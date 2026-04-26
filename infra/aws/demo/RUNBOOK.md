# Phase 1 — AWS bring-up runbook

> Per-step prompts. Run each one in order on your local laptop with `aws` CLI configured. Stop and verify before moving to the next.

## Prerequisites — gather before starting

- [ ] **Tailscale auth key** — from https://login.tailscale.com → Settings → Keys → Generate auth key. Reusable + Ephemeral + Pre-approved, expiry 24h. Save the `tskey-auth-...` string.
- [ ] **Route 53 zone ID** for `dynamo.works` — see step 0 below.
- [ ] **AWS account access** — `aws sts get-caller-identity` should print your identity. Region defaults to `us-east-1` here; override `AWS_REGION` if you want elsewhere.
- [ ] **A Supabase project (Phase 2) is already provisioned**, OR you're OK launching with a placeholder DATABASE_URL (the EC2 will come up but control-plane will crash; Caddy + Tailscale + cert will all work).

If you're not ready with Supabase yet, set `SUPABASE_DATABASE_URL=postgresql://demo:demo@nowhere:5432/demo` for now. Fix it later by editing `/opt/almighty/infra/aws/demo/.env` on the EC2 and running `docker compose --env-file .env up -d`.

---

## Step 0 — Stash secrets locally

Pick a local file you'll source from later steps. Don't commit this anywhere.

```bash
cat > ~/.almighty-demo-secrets.env <<'EOF'
TAILSCALE_AUTH_KEY=tskey-auth-PASTE-YOURS-HERE
ROUTE53_ZONE_ID=
AWS_REGION=us-east-1
SUPABASE_DATABASE_URL=postgresql://demo:demo@nowhere:5432/demo
JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\nREPLACE\n-----END PUBLIC KEY-----"
ALMIGHTY_BRANCH=hackathon-demo-2026-04-26
EOF
chmod 600 ~/.almighty-demo-secrets.env
```

Then capture the Route 53 zone ID:

```bash
aws route53 list-hosted-zones \
  --query 'HostedZones[?Name==`dynamo.works.`].Id' \
  --output text
```

This returns something like `/hostedzone/Z0123456789ABCDEFG`. Add the zone ID **without the `/hostedzone/` prefix** to the env file:

```bash
# Edit ~/.almighty-demo-secrets.env and set ROUTE53_ZONE_ID=Z0123456789ABCDEFG
```

Then load:

```bash
source ~/.almighty-demo-secrets.env
test -n "$TAILSCALE_AUTH_KEY" && test -n "$ROUTE53_ZONE_ID" && echo "secrets loaded"
```

---

## Step 1 — Generate JWT keypair (for control-plane auth)

```bash
mkdir -p ~/.almighty-demo-secrets
openssl genrsa -out ~/.almighty-demo-secrets/jwt.pem 2048
openssl rsa -in ~/.almighty-demo-secrets/jwt.pem -pubout > ~/.almighty-demo-secrets/jwt.pub

# Update the env file with the public key contents (\n-escaped):
PUBKEY=$(awk 'BEGIN{ORS="\\n"}1' ~/.almighty-demo-secrets/jwt.pub | sed 's/\\n$//')
# Replace the JWT_PUBLIC_KEY line in your secrets file with:
echo "JWT_PUBLIC_KEY=\"$PUBKEY\""
```

Edit `~/.almighty-demo-secrets.env` and replace the `JWT_PUBLIC_KEY` line with the value printed above. Then re-source:

```bash
source ~/.almighty-demo-secrets.env
```

---

## Step 2 — Create the IAM role for the EC2 instance

```bash
aws iam create-role \
  --role-name almighty-demo-ec2 \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{
      "Effect":"Allow",
      "Principal":{"Service":"ec2.amazonaws.com"},
      "Action":"sts:AssumeRole"
    }]
  }'
```

Verify:

```bash
aws iam get-role --role-name almighty-demo-ec2 --query 'Role.Arn' --output text
```

---

## Step 3 — Attach the Route 53 DNS-01 inline policy

```bash
cd /Users/shanemorris/Dev/almighty/infra/aws/demo

# Substitute the zone id into the policy template
sed "s|DYNAMO_WORKS_ZONE_ID_PLACEHOLDER|$ROUTE53_ZONE_ID|" \
  iam-policy-route53-dns01.json > /tmp/almighty-demo-policy.json

aws iam put-role-policy \
  --role-name almighty-demo-ec2 \
  --policy-name route53-dns01 \
  --policy-document file:///tmp/almighty-demo-policy.json
```

Verify:

```bash
aws iam list-role-policies --role-name almighty-demo-ec2
# expect: [route53-dns01]
```

---

## Step 4 — Create the instance profile and attach the role

```bash
aws iam create-instance-profile --instance-profile-name almighty-demo-ec2

aws iam add-role-to-instance-profile \
  --instance-profile-name almighty-demo-ec2 \
  --role-name almighty-demo-ec2

# IAM is eventually consistent — instance launch races with this.
# Sleep gives propagation a chance.
sleep 15
```

Verify:

```bash
aws iam get-instance-profile \
  --instance-profile-name almighty-demo-ec2 \
  --query 'InstanceProfile.Roles[0].RoleName' --output text
# expect: almighty-demo-ec2
```

---

## Step 5 — Find the default VPC

```bash
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query 'Vpcs[0].VpcId' --output text \
  --region "$AWS_REGION")
echo "VPC_ID=$VPC_ID"
```

If you don't have a default VPC, substitute a VPC + subnet of your choice. The bring-up assumes a public-subnet default VPC because that's the path of least resistance for a one-day demo.

---

## Step 6 — Create the security group

Outbound-only by default. The only inbound rule is UDP 41641 for Tailscale's WireGuard so the tunnel can establish.

```bash
SG_ID=$(aws ec2 create-security-group \
  --group-name almighty-demo-sg \
  --description "almighty-demo: outbound only; tailscale handles ingress" \
  --vpc-id "$VPC_ID" \
  --region "$AWS_REGION" \
  --query 'GroupId' --output text)
echo "SG_ID=$SG_ID"

aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol udp --port 41641 --cidr 0.0.0.0/0 \
  --region "$AWS_REGION"
```

> If you re-run and the SG already exists, the create call errors with "InvalidGroup.Duplicate". Look it up instead:
> ```bash
> SG_ID=$(aws ec2 describe-security-groups \
>   --filters "Name=group-name,Values=almighty-demo-sg" "Name=vpc-id,Values=$VPC_ID" \
>   --query 'SecurityGroups[0].GroupId' --output text --region "$AWS_REGION")
> ```

---

## Step 7 — Find the latest Ubuntu 24.04 amd64 AMI

```bash
AMI_ID=$(aws ec2 describe-images \
  --owners 099720109477 \
  --filters \
    "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
    "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text --region "$AWS_REGION")
echo "AMI_ID=$AMI_ID"
```

---

## Step 8 — Render the cloud-init userdata

Substitute the secrets into the template. Use BSD sed (macOS) or GNU sed accordingly.

```bash
cd /Users/shanemorris/Dev/almighty/infra/aws/demo

cp cloud-init.sh /tmp/almighty-userdata.sh

# macOS sed (-i ''); on Linux drop the empty quote argument
sed -i '' \
  -e "s|__TAILSCALE_AUTH_KEY__|$TAILSCALE_AUTH_KEY|g" \
  -e "s|__AWS_REGION__|$AWS_REGION|g" \
  -e "s|__SUPABASE_DATABASE_URL__|$SUPABASE_DATABASE_URL|g" \
  -e "s|__ALMIGHTY_BRANCH__|$ALMIGHTY_BRANCH|g" \
  /tmp/almighty-userdata.sh

# JWT_PUBLIC_KEY contains literal \n that need preservation; use a different delimiter
# and write through python to avoid sed escaping pain:
python3 - <<PY
import os
path = '/tmp/almighty-userdata.sh'
with open(path) as f: src = f.read()
src = src.replace('__JWT_PUBLIC_KEY__', os.environ['JWT_PUBLIC_KEY'])
with open(path, 'w') as f: f.write(src)
PY

# Sanity-check no placeholders remain
grep -E '__[A-Z_]+__' /tmp/almighty-userdata.sh && echo "WARN: unsubstituted placeholders" || echo "OK: all substituted"
```

---

## Step 9 — Launch the EC2 instance

```bash
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t3.medium \
  --iam-instance-profile "Name=almighty-demo-ec2" \
  --security-group-ids "$SG_ID" \
  --user-data "file:///tmp/almighty-userdata.sh" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=almighty-demo}]" \
  --region "$AWS_REGION" \
  --query 'Instances[0].InstanceId' --output text)

echo "INSTANCE_ID=$INSTANCE_ID"
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"
echo "instance running"
```

---

## Step 10 — Watch cloud-init progress (~5-7 min)

Open SSM Session Manager into the instance to tail logs:

```bash
aws ssm start-session --target "$INSTANCE_ID" --region "$AWS_REGION"
# Inside the session:
sudo tail -f /var/log/almighty-cloud-init.log
```

You're done when you see:

```
almighty-demo cloud-init complete at 2026-04-26T...
Tailscale IP: 100.x.y.z
Manual next step: create Route 53 A record
```

While still in the SSM session, capture the Tailscale IP for the next step:

```bash
sudo cat /etc/almighty/tailscale-ip
```

Exit SSM with `exit`.

---

## Step 11 — Manually create the Route 53 A record

In the AWS Route 53 console:

1. Hosted zones → `dynamo.works`
2. Create record
3. Record name: `almighty-demo`
4. Record type: `A`
5. Value: paste the Tailscale IP from step 10
6. TTL: `60`
7. Routing policy: Simple
8. Create

Or via CLI if you'd rather:

```bash
TS_IP=<paste from step 10>
aws route53 change-resource-record-sets \
  --hosted-zone-id "$ROUTE53_ZONE_ID" \
  --change-batch "{\"Changes\":[{\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"almighty-demo.dynamo.works\",\"Type\":\"A\",\"TTL\":60,\"ResourceRecords\":[{\"Value\":\"$TS_IP\"}]}}]}"
```

---

## Step 12 — Verify from your laptop

DNS resolves publicly:

```bash
dig +short almighty-demo.dynamo.works
# expect: 100.x.y.z (the Tailscale IP)
```

With your laptop on the Dynamo tailnet, the URL responds with a real cert:

```bash
curl -v https://almighty-demo.dynamo.works/
```

Expected: TLS handshake completes, valid Let's Encrypt cert chain, response from Caddy. If the upstream control-plane is down (placeholder DATABASE_URL, no Supabase yet), you'll get a 502 from Caddy — that's fine for now, it proves Caddy + cert + Tailscale routing all work.

If TLS fails: SSM in and check Caddy logs:

```bash
aws ssm start-session --target "$INSTANCE_ID" --region "$AWS_REGION"
sudo docker logs almighty-demo-caddy-1 --tail 100
```

Common issue: Caddy hits Let's Encrypt's prod rate limit (5 certs/week per registered domain) if you re-launch the EC2 several times. Switch to LE staging by adding `acme_ca https://acme-staging-v02.api.letsencrypt.org/directory` inside the Caddyfile's site block, accept the staging cert in your browser.

---

## Cleanup (when the demo is over)

```bash
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"
# Tailscale device auto-removes (we used --ephemeral)

# Optional: delete IAM + SG. Leave them if you'll re-run the demo.
aws iam remove-role-from-instance-profile \
  --instance-profile-name almighty-demo-ec2 --role-name almighty-demo-ec2
aws iam delete-instance-profile --instance-profile-name almighty-demo-ec2
aws iam delete-role-policy --role-name almighty-demo-ec2 --policy-name route53-dns01
aws iam delete-role --role-name almighty-demo-ec2
aws ec2 delete-security-group --group-id "$SG_ID" --region "$AWS_REGION"

# Delete Route 53 record manually in the console.
```

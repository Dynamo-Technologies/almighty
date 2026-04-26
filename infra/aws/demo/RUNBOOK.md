# Phase 1 — AWS bring-up runbook

> Per-step prompts. Run each on your laptop with `aws` CLI configured. Stop and verify before moving to the next.

## Architecture

`almightyengine.com` is registered in the same AWS account as the EC2 instance, so we can use the standard pattern: an EC2 instance role grants Caddy `route53:ChangeResourceRecordSets` permission, Caddy completes the DNS-01 challenge automatically, and Let's Encrypt issues a real cert. No cross-account IAM, no embedded credentials.

The instance has no public ingress beyond UDP 41641 (Tailscale WireGuard). Audience laptops on the Dynamo tailnet hit `https://almightyengine.com` and Tailscale routes the traffic to the EC2's `100.x.y.z` address.

## Prerequisites — gather before starting

- [ ] **Domain registered.** `almightyengine.com` is registered through Route 53 (or transferred in). Route 53 auto-creates the public hosted zone when you register through them.
- [ ] **Hosted zone ID** — `aws route53 list-hosted-zones --query 'HostedZones[?Name==\`almightyengine.com.\`].Id' --output text`. Strip the `/hostedzone/` prefix.
- [ ] **Tailscale auth key** — `tskey-auth-...` (reusable + ephemeral + pre-approved, 24h)
- [ ] **AWS account access** — `aws sts get-caller-identity` from your default profile prints your identity. This is where the EC2 + Route 53 zone both live.
- [ ] **Supabase project (Phase 2) provisioned**, OR you're OK launching with a placeholder DATABASE_URL

If you're not ready with Supabase yet, the placeholder `SUPABASE_DATABASE_URL=postgresql://demo:demo@nowhere:5432/demo` is fine. The EC2 will come up but control-plane will crash; Caddy + cert + Tailscale all work.

---

## Step 0 — Stash secrets locally

```bash
cat > ~/.almighty-demo-secrets.env <<'EOF'
TAILSCALE_AUTH_KEY=tskey-auth-PASTE_HERE
ALMIGHTYENGINE_ZONE_ID=PASTE_HERE
AWS_REGION=us-east-1
SUPABASE_DATABASE_URL=postgresql://demo:demo@nowhere:5432/demo
JWT_PUBLIC_KEY=
ALMIGHTY_BRANCH=hackathon-demo-2026-04-26
EOF
chmod 600 ~/.almighty-demo-secrets.env
```

Get the zone ID:

```bash
aws route53 list-hosted-zones \
  --query 'HostedZones[?Name==`almightyengine.com.`].Id' \
  --output text
```

That returns `/hostedzone/Zxxxxxxxxx`. Add `Zxxxxxxxxx` (no prefix) to the env file. Then load:

```bash
source ~/.almighty-demo-secrets.env
test -n "$TAILSCALE_AUTH_KEY" && test -n "$ALMIGHTYENGINE_ZONE_ID" && echo "OK"
```

---

## Step 1 — Generate JWT keypair (control-plane auth)

```bash
mkdir -p ~/.almighty-demo-secrets
openssl genrsa -out ~/.almighty-demo-secrets/jwt.pem 2048
openssl rsa -in ~/.almighty-demo-secrets/jwt.pem -pubout > ~/.almighty-demo-secrets/jwt.pub
PUBKEY=$(awk 'BEGIN{ORS="\\n"}1' ~/.almighty-demo-secrets/jwt.pub | sed 's/\\n$//')
echo "JWT_PUBLIC_KEY=\"$PUBKEY\""
```

Copy the printed line and replace the empty `JWT_PUBLIC_KEY=` line in `~/.almighty-demo-secrets.env`. Then re-`source`.

---

## Step 2 — Create the IAM role

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

sed "s|ALMIGHTYENGINE_ZONE_ID_PLACEHOLDER|$ALMIGHTYENGINE_ZONE_ID|" \
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

# IAM is eventually consistent. Sleep gives propagation a chance.
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
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" \
  --query 'Vpcs[0].VpcId' --output text --region "$AWS_REGION")
echo "VPC_ID=$VPC_ID"
```

---

## Step 6 — Create the security group

Outbound-only by default; the only inbound rule is UDP 41641 for Tailscale's WireGuard so the tunnel can establish.

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

> If the SG already exists from a previous attempt:
> ```bash
> SG_ID=$(aws ec2 describe-security-groups \
>   --filters "Name=group-name,Values=almighty-demo-sg" "Name=vpc-id,Values=$VPC_ID" \
>   --query 'SecurityGroups[0].GroupId' --output text --region "$AWS_REGION")
> ```

---

## Step 7 — Find the latest Ubuntu 24.04 amd64 AMI

```bash
AMI_ID=$(aws ec2 describe-images --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
            "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text --region "$AWS_REGION")
echo "AMI_ID=$AMI_ID"
```

---

## Step 8 — Render cloud-init userdata

Substitute the secrets into the template.

```bash
cd /Users/shanemorris/Dev/almighty/infra/aws/demo
cp cloud-init.sh /tmp/almighty-userdata.sh

# Simple substitutions — macOS sed (-i ''); Linux: drop the empty quote
sed -i '' \
  -e "s|__TAILSCALE_AUTH_KEY__|$TAILSCALE_AUTH_KEY|g" \
  -e "s|__AWS_REGION__|$AWS_REGION|g" \
  -e "s|__ALMIGHTY_BRANCH__|$ALMIGHTY_BRANCH|g" \
  -e "s|__SUPABASE_DATABASE_URL__|$SUPABASE_DATABASE_URL|g" \
  /tmp/almighty-userdata.sh

# Multi-line value via python (sed is painful with embedded newlines)
python3 - <<'PY'
import os
p = '/tmp/almighty-userdata.sh'
src = open(p).read().replace('__JWT_PUBLIC_KEY__', os.environ.get('JWT_PUBLIC_KEY', ''))
open(p, 'w').write(src)
PY

grep -E '__[A-Z_]+__' /tmp/almighty-userdata.sh && echo "WARN unsubstituted" || echo "OK all substituted"
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

## Step 10 — Wait for cloud-init + grab the Tailscale IP

Cloud-init runs ~5-7 minutes. Once it joins the tailnet (within ~30s of boot) you can `tailscale ssh` in:

```bash
# From your laptop with tailnet membership:
tailscale ssh ubuntu@almighty-demo "sudo tail -f /var/log/almighty-cloud-init.log"
```

If `tailscale ssh ubuntu@almighty-demo` doesn't resolve yet, wait 30 seconds and try again.

You're done when you see:

```
almighty-demo cloud-init complete at 2026-04-26T...
Tailscale IP: 100.x.y.z
Manual next step: create Route 53 A record
  almightyengine.com  →  100.x.y.z
```

Capture the Tailscale IP:

```bash
TS_IP=$(tailscale ssh ubuntu@almighty-demo "sudo cat /etc/almighty/tailscale-ip")
echo "TS_IP=$TS_IP"
```

---

## Step 11 — Create the Route 53 A record

You can use the AWS console (Route 53 → `almightyengine.com` → Create record, name blank for apex, type A, value the Tailscale IP, TTL 60), or the CLI:

```bash
aws route53 change-resource-record-sets \
  --hosted-zone-id "$ALMIGHTYENGINE_ZONE_ID" \
  --change-batch "{\"Changes\":[{\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"almightyengine.com\",\"Type\":\"A\",\"TTL\":60,\"ResourceRecords\":[{\"Value\":\"$TS_IP\"}]}}]}"
```

---

## Step 12 — Verify from your laptop

DNS resolves publicly:

```bash
dig +short almightyengine.com
# expect: 100.x.y.z (the Tailscale IP)
```

With your laptop on the Dynamo tailnet, hit the URL:

```bash
curl -v https://almightyengine.com/
```

Expected: real Let's Encrypt cert chain, green padlock. Response may be a 502 if the upstream control-plane is still booting (or the placeholder DATABASE_URL is set) — that's fine, it proves Caddy + cert + Tailscale routing all work.

If TLS handshake fails, tail Caddy's logs:

```bash
tailscale ssh ubuntu@almighty-demo "cd /opt/almighty/infra/aws/demo && docker compose logs caddy --tail 100"
```

Common failure modes:
- **DNS-01 timed out / Route 53 access denied.** Check that the EC2 instance role has the route53-dns01 inline policy. Caddy retries on the next restart.
- **Let's Encrypt rate-limited.** If you've relaunched the EC2 several times, LE's "5 certs/week per registered domain" kicks in. Switch to LE staging by adding `acme_ca https://acme-staging-v02.api.letsencrypt.org/directory` inside the Caddyfile site block; accept the staging cert in the browser.

---

## Cleanup (when the demo is over)

```bash
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"
# Tailscale device auto-removes (we used --ephemeral)

aws iam remove-role-from-instance-profile \
  --instance-profile-name almighty-demo-ec2 --role-name almighty-demo-ec2
aws iam delete-instance-profile --instance-profile-name almighty-demo-ec2
aws iam delete-role-policy --role-name almighty-demo-ec2 --policy-name route53-dns01
aws iam delete-role --role-name almighty-demo-ec2
aws ec2 delete-security-group --group-id "$SG_ID" --region "$AWS_REGION"

# Delete the Route 53 A record manually in the console if you want.
```

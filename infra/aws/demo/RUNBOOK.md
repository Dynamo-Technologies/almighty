# Phase 1 — AWS bring-up runbook

> Per-step prompts. Run each on your laptop with `aws` CLI configured. Stop and verify before moving to the next.

## Architecture note

Route 53 lives in a different AWS account (`639623969283`) from the EC2 we're launching. Caddy on EC2 uses **explicit STS credentials** for its one-shot DNS-01 cert acquisition rather than an IAM cross-account assume-role dance — temporary creds expire in a few hours but the resulting LE cert lasts 90 days, more than enough for a single-day demo.

Because of this, the EC2 instance role is **dropped entirely**. Shell access uses Tailscale SSH (`tailscale ssh ubuntu@almighty-demo`). SSM is not configured.

## Prerequisites

- [ ] **Tailscale auth key** — `tskey-auth-...` (reusable + ephemeral + pre-approved, 24h)
- [ ] **Route 53 STS creds** — temp credentials (`ASIA...`) for an AWS_Route_53 SSO role with `route53:ChangeResourceRecordSets` on `dynamo.works`
- [ ] **EC2-account AWS access** — `aws sts get-caller-identity` from your default profile prints your identity. This is the account where the EC2 will live (different from the Route 53 account).
- [ ] **Supabase project (Phase 2) provisioned**, OR you're OK launching with a placeholder DATABASE_URL

---

## Step 0 — Stash secrets locally

```bash
cat > ~/.almighty-demo-secrets.env <<'EOF'
TAILSCALE_AUTH_KEY=tskey-auth-PASTE_HERE
AWS_REGION=us-east-1
SUPABASE_DATABASE_URL=postgresql://demo:demo@nowhere:5432/demo
JWT_PUBLIC_KEY=
ALMIGHTY_BRANCH=hackathon-demo-2026-04-26
# Route 53 cross-account creds (used by Caddy DNS-01 cert acquisition).
# Get these from your AWS Identity Center → Route 53 account → CLI creds.
ROUTE53_AWS_ACCESS_KEY_ID=
ROUTE53_AWS_SECRET_ACCESS_KEY=
ROUTE53_AWS_SESSION_TOKEN=
EOF
chmod 600 ~/.almighty-demo-secrets.env
```

Edit and fill in the blanks. The hosted zone ID for `dynamo.works` is `ZS94FAYT9V2E7` — you'll only need it manually for step 11.

```bash
source ~/.almighty-demo-secrets.env
test -n "$TAILSCALE_AUTH_KEY" && \
test -n "$ROUTE53_AWS_ACCESS_KEY_ID" && \
test -n "$JWT_PUBLIC_KEY" && \
echo "OK secrets loaded"
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

Copy the printed line and replace the empty `JWT_PUBLIC_KEY=` line in `~/.almighty-demo-secrets.env`. Then re-source.

---

## Step 2 — Find your default VPC

```bash
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" \
  --query 'Vpcs[0].VpcId' --output text --region "$AWS_REGION")
echo "VPC_ID=$VPC_ID"
```

---

## Step 3 — Create the security group

Outbound-only by default. The single inbound rule is UDP 41641 for Tailscale's WireGuard so the tunnel can establish.

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

## Step 4 — Find the latest Ubuntu 24.04 amd64 AMI

```bash
AMI_ID=$(aws ec2 describe-images --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
            "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text --region "$AWS_REGION")
echo "AMI_ID=$AMI_ID"
```

---

## Step 5 — Render cloud-init userdata

Substitute the secrets into the template.

```bash
cd /Users/shanemorris/Dev/almighty/infra/aws/demo
cp cloud-init.sh /tmp/almighty-userdata.sh

# Simple substitutions — macOS sed (-i ''); Linux drop the ''
sed -i '' \
  -e "s|__TAILSCALE_AUTH_KEY__|$TAILSCALE_AUTH_KEY|g" \
  -e "s|__AWS_REGION__|$AWS_REGION|g" \
  -e "s|__ALMIGHTY_BRANCH__|$ALMIGHTY_BRANCH|g" \
  -e "s|__SUPABASE_DATABASE_URL__|$SUPABASE_DATABASE_URL|g" \
  /tmp/almighty-userdata.sh

# Multi-line / special-char-prone values via python
python3 - <<'PY'
import os
p = '/tmp/almighty-userdata.sh'
src = open(p).read()
for k in ('JWT_PUBLIC_KEY',
          'ROUTE53_AWS_ACCESS_KEY_ID',
          'ROUTE53_AWS_SECRET_ACCESS_KEY',
          'ROUTE53_AWS_SESSION_TOKEN'):
    src = src.replace('__' + k + '__', os.environ.get(k, ''))
open(p, 'w').write(src)
PY

grep -E '__[A-Z_]+__' /tmp/almighty-userdata.sh && echo "WARN unsubstituted" || echo "OK all substituted"
```

---

## Step 6 — Launch the EC2 instance (no IAM role)

```bash
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t3.medium \
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

## Step 7 — Wait for cloud-init + grab the Tailscale IP

Cloud-init runs ~5-7 minutes. Once it joins the tailnet (within ~30s of boot) you can `tailscale ssh` in:

```bash
# From your laptop with tailnet membership:
tailscale ssh ubuntu@almighty-demo "sudo tail -f /var/log/almighty-cloud-init.log"
```

If `tailscale ssh ubuntu@almighty-demo` doesn't resolve yet, wait 30 seconds and try again — Tailscale needs a moment to advertise the host.

You're done when you see:

```
almighty-demo cloud-init complete at 2026-04-26T...
Tailscale IP: 100.x.y.z
Manual next step: create Route 53 A record
```

Capture the Tailscale IP:

```bash
TS_IP=$(tailscale ssh ubuntu@almighty-demo "sudo cat /etc/almighty/tailscale-ip")
echo "TS_IP=$TS_IP"
```

---

## Step 8 — Create the Route 53 A record (using the cross-account creds)

```bash
AWS_ACCESS_KEY_ID=$ROUTE53_AWS_ACCESS_KEY_ID \
AWS_SECRET_ACCESS_KEY=$ROUTE53_AWS_SECRET_ACCESS_KEY \
AWS_SESSION_TOKEN=$ROUTE53_AWS_SESSION_TOKEN \
aws route53 change-resource-record-sets \
  --hosted-zone-id ZS94FAYT9V2E7 \
  --change-batch "{\"Changes\":[{\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"almighty-demo.dynamo.works\",\"Type\":\"A\",\"TTL\":60,\"ResourceRecords\":[{\"Value\":\"$TS_IP\"}]}}]}"
```

Or, if you'd rather click in the Route 53 console: zone → Create record, name `almighty-demo`, type `A`, value the IP, TTL 60.

---

## Step 9 — Verify from your laptop

```bash
dig +short almighty-demo.dynamo.works
# expect: 100.x.y.z (the Tailscale IP)

curl -v https://almighty-demo.dynamo.works/
```

Expected: real LE cert chain, green padlock. Response may be a 502 from Caddy if the upstream control-plane is still booting (or DATABASE_URL is the placeholder) — that's fine, it proves Caddy + cert + Tailscale routing all work.

If TLS handshake fails: tail Caddy's logs:

```bash
tailscale ssh ubuntu@almighty-demo "cd /opt/almighty/infra/aws/demo && docker compose logs caddy --tail 100"
```

Most likely failure: the Route 53 STS creds expired before Caddy issued the cert. Refresh your SSO session, update the three `ROUTE53_AWS_*` lines in `/opt/almighty/infra/aws/demo/.env` on the EC2, and `docker compose --env-file .env up -d` to restart.

---

## Cleanup

```bash
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"
# Tailscale device auto-removes (--ephemeral)
aws ec2 delete-security-group --group-id "$SG_ID" --region "$AWS_REGION"
# Delete Route 53 record manually in the console (different account).
```

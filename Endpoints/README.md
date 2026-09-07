# Ship Date Engine API Endpoints

This document covers only the HTTP endpoints exposed by the FastAPI service.

## Base URL

```text
http://localhost:8001
```

For a deployed server:

```text
http://<your-server-host>:8001
```

## DNS / Route 53 setup

If you want the API to be reachable by a friendly hostname such as `kplsh000.kaytheon.com`, create the DNS record in Amazon Route 53.

### 1) Confirm the hosted zone exists
In the AWS Console:
- Open Route 53
- Select Hosted zones
- If `kaytheon.com` does not exist, create a public hosted zone for that domain

### 2) Create the A record for the API host
Create a new record with these values:

```text
Record name: kplsh000
Type: A
Value: <EC2 public IP> or <Elastic IP>
TTL: 300
```

If the EC2 instance uses an Elastic IP, prefer the Elastic IP because it stays stable when the instance is restarted.

### 3) Save and verify propagation
After saving the record, test DNS resolution:

```bash
dig +short kplsh000.kaytheon.com
```

Expected result:

```text
<your-ec2-public-ip>
```

You can also check with AWS CLI:

```bash
aws route53 list-resource-record-sets --hosted-zone-id <HOSTED_ZONE_ID>
```

### 4) Expose the API on port 8001
Start the FastAPI service on all interfaces:

```bash
cd /home/kkhoja/Code/Ship-Date-Engine
python3.11 run_server.py --host 0.0.0.0 --port 8001
```

Open the EC2 security group and allow inbound TCP `8001`.

Then verify the DNS endpoint:

```bash
curl --max-time 10 http://kplsh000.kaytheon.com:8001/health
```

## Endpoints

### GET /
Returns the API root metadata.

Example response:

```json
{
  "service": "Ship Date Engine API",
  "status": "healthy",
  "docs": "/docs",
  "health": "/health"
}
```

### GET /health
Checks whether the API is running.

Example response:

```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

### POST /upload/{shipping_id}
Uploads a file and stores it for the given shipping ID.

Request:
- Method: `POST`
- Content-Type: `multipart/form-data`
- Path parameter: `shipping_id`
- Form field: `invoice` (required file upload)
- Form field: `priority` (optional integer, default `100`)

Validation:
- filename sanitization
- allowed file extension check
- file size limit enforcement

Example request:

```bash
curl -X POST "http://localhost:8001/upload/ABC123" \
  -F "invoice=@/path/to/document.xlsx" \
  -F "priority=100"
```

Example response:

```json
{
  "message": "Invoice uploaded successfully",
  "file": "/path/to/uploads/document.xlsx"
}
```

### POST /lookup/{shipping_id}
Retrieves a cached lookup result for a shipping ID.

Example request:

```bash
curl "http://localhost:8001/lookup/ABC123"
```

Example response when found:

```json
{
  "shipping_id": "ABC123",
  "cached": true,
  "result": {
    "status": "success"
  }
}
```

Example response when not found:

```json
{
  "message": "Shipping ID not found in cache",
  "shipping_id": "ABC123"
}
```

### GET /cache/cleanup
Deletes cached lookup entries older than the supplied number of days.

Query parameter:
- `days` (optional, default `30`)

Example:

```bash
curl "http://localhost:8001/cache/cleanup?days=30"
```

Example response:

```json
{
  "cleared": 12,
  "days_threshold": 30
}
```

## Run the API server

```bash
python run_server.py --host 0.0.0.0 --port 8001
```

Open the Swagger UI here:

```text
http://localhost:8001/docs
```

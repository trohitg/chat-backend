# Razorpay Webhook Configuration Guide

## Production Webhook URL
```
https://api.disutopia.xyz/api/v1/payments/webhook
```

## Setup Instructions

### 1. Configure Webhook in Razorpay Dashboard

1. Log in to [Razorpay Dashboard](https://dashboard.razorpay.com/)
2. Navigate to **Settings** → **Webhooks**
3. Click **Add New Webhook**
4. Enter the following details:
   - **Webhook URL**: `https://api.disutopia.xyz/api/v1/payments/webhook`
   - **Secret**: Generate a strong secret (save this for the next step)
   - **Alert Email**: Your notification email
   - **Active**: Enable the webhook

5. Select the following events:
   - ✅ `payment.captured` - Payment successful
   - ✅ `payment.failed` - Payment failed
   - ✅ `payment.authorized` - Payment authorized (for 2-step payments)
   - ✅ `order.paid` - Order fully paid
   - ✅ `refund.created` - Refund initiated (optional)
   - ✅ `refund.processed` - Refund completed (optional)

6. Click **Create Webhook**

### 2. Update Backend Configuration

Update the `.env` file in `chat-backend` with your webhook secret:

```env
RAZORPAY_WEBHOOK_SECRET="your_webhook_secret_from_dashboard"
```

### 3. Security Features Implemented

✅ **Signature Verification**: All webhooks are verified using HMAC SHA256
✅ **Idempotency**: Duplicate events are automatically detected and skipped
✅ **Event ID Tracking**: Each event is tracked by its unique ID
✅ **Error Handling**: Returns 2xx status to prevent retry storms
✅ **Background Processing**: Events are processed asynchronously

## Testing Webhooks

### Manual Test (Development)
```bash
# Test webhook endpoint (will fail signature verification - expected)
curl -X POST https://api.disutopia.xyz/api/v1/payments/webhook \
  -H "Content-Type: application/json" \
  -H "X-Razorpay-Signature: test_signature" \
  -H "X-Razorpay-Event-Id: test_event_123" \
  -d '{
    "event": "payment.captured",
    "payload": {
      "payment": {
        "entity": {
          "id": "pay_test123",
          "order_id": "order_test123",
          "amount": 10000,
          "status": "captured"
        }
      }
    }
  }'
```

### Using Razorpay Test Mode

1. Use test API keys in development
2. Create test payments in the dashboard
3. Razorpay will send real webhooks to your endpoint

### Webhook Event Flow

1. **Payment Initiated** → Flutter app creates order
2. **User Completes Payment** → Razorpay processes payment
3. **Webhook Sent** → Razorpay sends event to our endpoint
4. **Signature Verified** → Backend validates webhook authenticity
5. **Event Processed** → Payment status updated in database
6. **Response Sent** → 200 OK returned to Razorpay

## Supported Payment Events

| Event | Description | Action |
|-------|-------------|--------|
| `payment.captured` | Payment successful | Update status to "completed" |
| `payment.failed` | Payment failed | Update status to "failed" with error |
| `payment.authorized` | Payment authorized | Update status to "authorized" |
| `order.paid` | Order fully paid | Update status to "paid" |
| `refund.created` | Refund initiated | Log refund creation |
| `refund.processed` | Refund completed | Log refund completion |

## Monitoring Webhooks

Check webhook health and logs:

```bash
# View API logs
docker-compose logs -f chat-api

# Check webhook processing
curl https://api.disutopia.xyz/api/v1/health

# Database payment records
docker-compose exec postgres psql -U chatuser -d chatdb -c "SELECT * FROM payment_transactions ORDER BY created_at DESC LIMIT 5;"
```

## Troubleshooting

### Invalid Signature Error
- Verify webhook secret matches in dashboard and `.env`
- Ensure you're using the raw request body for verification

### Duplicate Events
- Normal behavior - events with same ID are automatically skipped
- Check `notes` field in database for processed event IDs

### Webhook Not Receiving
- Verify URL is publicly accessible
- Check Cloudflare tunnel is running
- Ensure webhook is active in Razorpay dashboard

## Flutter App Integration

The Flutter app is configured to:
1. Create orders via `/api/v1/payments/create-order`
2. Use Razorpay SDK for payment processing
3. Display payment status from webhook updates

## Security Best Practices

1. **Never expose webhook secret** in client code
2. **Always verify signatures** before processing
3. **Handle idempotency** to prevent duplicate processing
4. **Return 2xx status** even for errors to prevent retry storms
5. **Process asynchronously** to respond quickly
6. **Log all events** for audit trail

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/payments/create-order` | POST | Create Razorpay order |
| `/api/v1/payments/webhook` | POST | Webhook receiver |
| `/api/v1/payments/validate-vpa` | POST | Validate UPI VPA |
| `/api/v1/payments/status/{id}` | GET | Get payment status |

## Contact

For issues or questions about webhook integration, contact the development team.
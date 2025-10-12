# Customer Support Assistant Template

A pre-configured AI chatbot optimized for customer support operations.

## Features

- **Professional Tone**: Configured for empathetic, clear customer service
- **Document Analysis**: Can process attachments (receipts, screenshots, etc.)
- **Conversation History**: Tracks customer interaction history
- **Escalation Protocols**: Built-in rules for human handoff
- **Content Filtering**: Prevents inappropriate responses

## What's Included

- `.env.example` - Complete configuration with customer support optimizations
- `system-prompt.txt` - Professional customer support prompt with guidelines
- `README.md` - This file with setup instructions

## Quick Start

### 1. Initialize Template

```bash
# From repo root
cd use-cases/customer-support
cp .env.example ../../.env
cp .env.example ../../frontend/.env.local
cp system-prompt.txt ../../src/chatbot_ai_system/config/system_prompt.txt
```

### 2. Customize for Your Business

Edit `.env` and update:
```bash
NEXT_PUBLIC_COMPANY="Your Company Name"
NEXT_PUBLIC_FOOTER_TEXT="© Your Company Name"
# Add your actual API keys
OPENAI_API_KEY="sk-..."
```

Edit `system-prompt.txt` and replace:
- `[COMPANY_NAME]` with your company name
- Add your specific policies, return windows, etc. in the "Company-Specific Information" section

### 3. Launch

```bash
# Backend
poetry install
poetry run uvicorn chatbot_ai_system.server.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Visit http://localhost:3000

## Configuration Highlights

### Model Settings
- **Default Model**: GPT-4 (higher quality for customer interactions)
- **Temperature**: 0.5 (balanced between consistency and natural responses)
- **Max Tokens**: 1500 (concise but complete answers)

### UI Customization
- **Theme**: Light mode (professional, accessible)
- **Primary Color**: Green (trust, helpfulness)
- **Timestamps**: Enabled (accountability)
- **Model Badge**: Hidden (customers don't need to see this)

### Security & Safety
- **Content Filtering**: Enabled (prevents inappropriate responses)
- **File Upload**: Enabled (customers can share screenshots/receipts)
- **Model Selection**: Disabled (customers use pre-configured model)

## Best Practices

### System Prompt Customization
1. Add your actual return/refund policies
2. List your most common products/services
3. Define your escalation contacts
4. Include your business hours
5. Add any compliance/legal disclaimers

### Monitoring
- Track escalation frequency (if high, improve the system prompt)
- Monitor average resolution time
- Collect customer satisfaction ratings
- Review conversations that led to escalations

### Integration Options
Set these in `.env` when ready:
```bash
ENABLE_SLACK_INTEGRATION="true"      # Notify team in Slack
ENABLE_WEBHOOK_NOTIFICATIONS="true"  # Send escalations to ticketing system
```

## Example Customizations

### Add Product Knowledge
Edit `system-prompt.txt` to add:
```
### Our Products
- Product A: [description, price, key features]
- Product B: [description, price, key features]
- Product C: [description, price, key features]
```

### Add Policy Details
```
### Return Policy
- 30-day return window from delivery date
- Item must be unused with original packaging
- Refunds processed within 5-7 business days
- Customer pays return shipping unless item is defective
```

### Set Business Hours
```
### Support Hours
- Monday-Friday: 9 AM - 6 PM EST
- Saturday: 10 AM - 4 PM EST
- Sunday: Closed

Outside these hours, I can still help with basic questions, but complex issues will be addressed when the team returns.
```

## Troubleshooting

**Issue**: Chatbot is too formal
- **Solution**: Lower temperature to 0.7-0.8 in `.env`

**Issue**: Responses are too long
- **Solution**: Reduce `MAX_RESPONSE_LENGTH` in `.env`

**Issue**: Bot makes promises it shouldn't
- **Solution**: Strengthen "What You CANNOT Do" section in system prompt

**Issue**: Too many escalations
- **Solution**: Expand knowledge base in system prompt, add more FAQs

## Advanced: Multi-Language Support

To add Spanish support:
```bash
# In .env
CUSTOM_INSTRUCTIONS="Always ask the customer their preferred language at the start. Respond in Spanish if requested."
```

Then update system prompt with translation guidelines.

## Next Steps

1. ✅ Set up the template
2. ⬜ Customize with your company info
3. ⬜ Test with sample customer scenarios
4. ⬜ Train your team on escalation process
5. ⬜ Deploy to production
6. ⬜ Monitor and iterate

## Support

For issues with this template or the underlying platform, see the main repository README.

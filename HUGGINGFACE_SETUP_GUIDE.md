# 🤗 HuggingFace Setup Guide

## Quick Start: Connect Your HuggingFace Account

Follow these simple steps to unlock access to thousands of gated models!

---

## Step 1: Navigate to Settings

1. Click **"Settings"** in the sidebar (bottom of navigation)
2. You'll see the HuggingFace Integration card

**Status Badge:**
- 🔴 **Not Connected** - No token configured
- 🟢 **Connected** - Token saved and verified

---

## Step 2: Get Your HuggingFace Token

### **Option A: Direct Link**
1. Click the blue link: **"Get your token from HuggingFace"**
2. It will open: `https://huggingface.co/settings/tokens`

### **Option B: Manual**
1. Go to [HuggingFace.co](https://huggingface.co)
2. Sign in to your account
3. Click your profile → **Settings**
4. Navigate to **Access Tokens**
5. Click **"New token"**

### **Token Configuration**
- **Name:** `CraftML Studio` (or any name you prefer)
- **Type:** **Read** (recommended) or **Write** (if uploading models)
- **Scope:** Select repositories (optional)

---

## Step 3: Save Token in CraftML

1. Copy your token (starts with `hf_`)
2. Paste it into the **"Access Token"** field
3. Click **"Save Token"**

**Verification Process:**
```
Saving...
  ↓
Verifying with HuggingFace...
  ↓
✅ Token saved successfully!
  ↓
Shows your username
```

---

## Step 4: Verify Connection

After saving, you'll see:

```
┌─────────────────────────────────────────────┐
│ ✅ Connected                                │
│                                              │
│ Connected Account                            │
│ your_username                                │
│ Token: hf_••••••••••••                      │
│                                              │
│ [Remove Token]                               │
└─────────────────────────────────────────────┘
```

---

## Using Your Connected Account

### **Downloading Gated Models**

Now you can download models that require authentication:

1. **Meta Llama Models**
   - `meta-llama/Llama-2-7b-hf`
   - `meta-llama/Llama-2-13b-hf`
   - `meta-llama/Llama-3-8B`

2. **Mistral AI Models**
   - `mistralai/Mistral-7B-v0.1`
   - `mistralai/Mixtral-8x7B-v0.1`

3. **Community Models**
   - Any model marked as "gated"
   - Private repositories
   - Organization models

### **How It Works**

```
You: "Download meta-llama/Llama-2-7b-hf"
  ↓
CraftML: Checks for HF token
  ↓
Found token ✅
  ↓
Uses token for authenticated download
  ↓
Downloads model successfully!
```

**Without Token:**
```
You: "Download meta-llama/Llama-2-7b-hf"
  ↓
CraftML: No token found
  ↓
Tries unauthenticated download
  ↓
❌ Error: Repository requires authentication
```

---

## Token Security

### **Where is my token stored?**

```
Your Computer
  └── User Home Directory (~/)
      └── .craftml/
          └── settings/
              ├── .key (encryption key)
              ├── hf_token.enc (encrypted token)
              └── hf_metadata.json (username, preview)
```

### **Is it secure?**

✅ **Yes!** Your token is:
- **Encrypted** using Fernet (industry-standard)
- **Stored locally** (never sent to external servers except HuggingFace)
- **Hidden** from logs and UI (shows `hf_••••••••••••`)
- **Revocable** anytime from HuggingFace settings
- **Deletable** from CraftML Settings

---

## Troubleshooting

### **❌ "Invalid token format"**

**Problem:** Token doesn't start with `hf_`

**Solution:**
- Copy the entire token from HuggingFace
- Make sure you copied the token, not the token name
- Token should look like: `hf_AbCdEfGhIjKlMnOpQrStUvWxYz`

---

### **❌ "Invalid token: Could not verify token"**

**Problem:** Token doesn't work with HuggingFace API

**Solution:**
- Check if token is still active on HuggingFace settings
- Create a new token
- Make sure you have internet connection
- Verify HuggingFace is not down

---

### **❌ "Repository requires authentication"**

**Problem:** Trying to download gated model without token

**Solution:**
1. Go to Settings
2. Save your HuggingFace token
3. Request access to the model on HuggingFace
4. Try downloading again

---

### **🔄 "Model downloads but says '401 Unauthorized'"**

**Problem:** Token saved but model still requires authentication

**Solution:**
1. Go to the model page on HuggingFace
2. Click "Request Access" or "Agree to Terms"
3. Wait for approval (usually instant)
4. Try downloading again in CraftML

---

### **🗑️ Removing Your Token**

If you want to disconnect:

1. Go to **Settings**
2. Click **"Remove Token"**
3. Confirm deletion
4. Status changes to **"Not Connected"**

**Note:** This only removes the token from CraftML. Your token is still active on HuggingFace. To fully revoke it, delete it from HuggingFace settings.

---

## Token Permissions Guide

### **Read Access (Recommended)**
✅ Download public models  
✅ Download gated models (with approval)  
✅ Access private repositories (yours only)  
✅ Higher rate limits  
❌ Cannot upload models  

### **Write Access (Advanced)**
✅ All Read permissions  
✅ Upload models  
✅ Create repositories  
✅ Modify model cards  
⚠️ More powerful (use carefully)  

**For most users, Read access is sufficient!**

---

## Example: Downloading Llama 2

### **Step-by-Step**

1. **Request Access on HuggingFace**
   - Go to `https://huggingface.co/meta-llama/Llama-2-7b-hf`
   - Click "Agree and access repository"
   - Wait for approval (usually instant)

2. **Connect CraftML**
   - Go to Settings in CraftML
   - Save your HuggingFace token
   - Verify "Connected" status

3. **Download Model**
   - Go to Training Console or Model Hub
   - Search: `meta-llama/Llama-2-7b-hf`
   - Click "Download"
   - Wait for download to complete

4. **Start Training**
   - Select downloaded model
   - Configure training parameters
   - Start fine-tuning!

---

## FAQ

### **Do I need a HuggingFace account?**
Yes, you need a free HuggingFace account to generate tokens.

### **Is the token free?**
Yes, HuggingFace tokens are completely free.

### **How many tokens can I create?**
HuggingFace allows multiple tokens per account.

### **Can I use the same token on multiple devices?**
Yes, but it's better to create separate tokens for each device for security.

### **What if I forget to remove my token before uninstalling?**
The token file stays on your computer. Either:
- Delete `~/.craftml/` folder manually
- Revoke token from HuggingFace settings

### **Can team members share a token?**
Not recommended. Each team member should use their own token.

### **Does this work offline?**
- Token saving: ❌ No (needs to verify with HuggingFace)
- Token loading: ✅ Yes (stored locally)
- Model downloads: ❌ No (downloads from HuggingFace)

---

## Support

### **Need Help?**

1. Check the [HuggingFace Documentation](https://huggingface.co/docs)
2. Review error messages in Settings page
3. Check console logs for debugging
4. Ensure internet connection is stable

### **Common Issues**

| Error | Cause | Solution |
|-------|-------|----------|
| 401 Unauthorized | No access to model | Request access on HuggingFace |
| 403 Forbidden | Invalid/revoked token | Create new token |
| 404 Not Found | Model doesn't exist | Check model name spelling |
| Network Error | No internet | Check connection |

---

## Best Practices

✅ **Do:**
- Use read-only tokens for security
- Create descriptive token names
- Revoke unused tokens
- Keep token secure
- Request model access before downloading

❌ **Don't:**
- Share tokens publicly
- Commit tokens to Git
- Use write tokens unless needed
- Store tokens in plaintext
- Use the same token for everything

---

## 🎉 You're All Set!

With your HuggingFace account connected, you now have access to:
- **1000+ gated models**
- **Private repositories**
- **Higher download speeds**
- **Community models**
- **Latest research models**

Happy fine-tuning! 🚀


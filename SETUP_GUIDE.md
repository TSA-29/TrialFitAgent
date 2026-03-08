# Quick Setup Guide - Setting Your STEP_API_KEY

## 🎯 Easiest Method: .env File (Recommended!)

1. **Copy the example file:**
   ```bash
   copy .env.example .env
   ```

2. **Edit the .env file** and replace the placeholder:
   ```bash
   STEP_API_KEY=sk-your-actual-api-key-here
   ```

3. **Done!** The app will automatically load the key from `.env` when you run it.

---

## 📝 Alternative Methods

### Method 2: Temporary (Current Session Only)

**Command Prompt:**
```cmd
set STEP_API_KEY=your_key_here
chainlit run ui.py -w
```

**PowerShell:**
```powershell
$env:STEP_API_KEY="your_key_here"
chainlit run ui.py -w
```

### Method 3: Permanent (System Environment Variable)

**Option A: Using setx command**
```cmd
setx STEP_API_KEY "your_key_here"
```
Then restart your terminal.

**Option B: Using Windows GUI**
1. Press `Windows Key` → Search **"Environment Variables"**
2. Click **"Edit the system environment variables"**
3. Click **"Environment Variables"** button
4. Under **"User variables"**, click **"New"**
5. Variable name: `STEP_API_KEY`
6. Variable value: `your_key_here`
7. Click **OK** and restart terminal

---

## ✅ Verify It's Set

Run this command to check:

**Command Prompt:**
```cmd
echo %STEP_API_KEY%
```

**PowerShell:**
```powershell
echo $env:STEP_API_KEY
```

If it shows your API key, you're ready to go! 🚀

---

## 🔒 Security Best Practices

- ✅ **DO** use `.env` file (already in `.gitignore`)
- ✅ **DO** keep your API key secret
- ❌ **DON'T** commit `.env` file to git
- ❌ **DON'T** share your API key with others

---

## 🆘 Troubleshooting

**Q: I get "Missing STEP_API_KEY" error**
A: Make sure you've set the API key using one of the methods above, then restart your terminal.

**Q: The .env file isn't working**
A: Make sure:
  - The file is named exactly `.env` (not `.env.txt`)
  - It's in the same folder as `ui.py`
  - You've installed python-dotenv: `pip install python-dotenv`

**Q: I need to change my API key**
A: Simply edit your `.env` file and update the key, or use `setx` again for environment variables.

# Virtual Advisor - Quick Start

## What's New? 🎉

Virtual Advisor now handles **application management** with a simple dropdown interface!

## Quick Access

1. Login to dashboard: `https://localhost:5000`
2. Click: **💡 Virtual Advisor** (bottom right)
3. Select action from dropdown
4. Type your request
5. Click "Send Request"

## Available Actions

| Action | Purpose | Example Request |
|--------|---------|----------------|
| **PS** (default) | Check status | "What's the current status?" |
| **START** | Deploy/start app | "Start my application" |
| **STOP** | Stop services | "Stop all containers" |
| **RESTART** | Reload services | "Restart the application" |
| **LOGS** | View logs | "Show me the logs" |

## Interface

```
┌────────────────────────────────┐
│ Action: [PS ▼]   USER_ID: 5   │
├────────────────────────────────┤
│ [Your message here...]         │
│                                │
│ [Send Request]                 │
└────────────────────────────────┘
```

## Example Conversations

### Check Status (PS)
```
Action: PS
Message: "What's the status of my deployment?"
Response: {
  "docker_compose_ps": "IS_RUNNING",
  "docker_ports": ["8080", "8081"],
  ...
}
```

### Start Application
```
Action: START
Message: "Deploy my application"
Response: "✅ Application started successfully on ports 8080/8081"
```

### View Logs
```
Action: LOGS
Message: "Show me the last 50 lines"
Response: [Container logs displayed]
```

## Features

✅ **No typing commands** - Just select from dropdown
✅ **See your USER_ID** - Always visible
✅ **Natural language** - Describe what you want
✅ **Context-aware** - Uses your user info automatically
✅ **Fast responses** - Optimized for speed

## Tips

💡 **Default is PS** - Quick status checks
💡 **Be specific** - "Start application X" vs "start"
💡 **Check USER_ID** - Verify it's correct before actions
💡 **Use natural language** - No need for exact commands

## Technical Details

- **Backend**: AI Chat with context from `./shared/` folder
- **Actions**: Mapped to `*_context.md` files
- **Execution**: Automatic with `--trust-all-tools`
- **User Context**: Auto-injected (ID, name, email)

## Documentation

- **Full Guide**: `VIRTUAL_ADVISOR_CHANGES.md`
- **UI Details**: `VIRTUAL_ADVISOR_UI_CHANGES.md`
- **Testing**: `TEST_VIRTUAL_ADVISOR.md`
- **Quick Reference**: `VIRTUAL_ADVISOR_QUICK_GUIDE.md`
- **Implementation**: `IMPLEMENTATION_SUMMARY.md`

## Troubleshooting

**Action not working?**
- Check if qchat is installed: `which qchat`
- Verify you're logged in
- Check application logs

**Wrong USER_ID?**
- Logout and login again
- Clear browser cache

**No response?**
- Check network connection
- Verify application is running
- Check logs: `tail -f /var/log/opcp-ai-powered-store.log`

## Support

Need help? Check:
1. This README
2. Documentation files in this folder
3. Application logs
4. Test with PS action first

---

**Version**: 1.0
**Last Updated**: 2026
**Status**: ✅ Production Ready

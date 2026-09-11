# Gmail Connection Setup

## Create the `gmail_connection.yaml` file

```yaml
spec_version: v1
kind: connection
app_id: gmail_connection
environments:
    draft:
        kind: key_value
        type: team
    live:
        kind: key_value
        type: team
```

## Import the Connection

Activate your Orchestrate environment:

```bash
orchestrate env activate your-environment-name
```

Add the connection:

```bash
orchestrate connections import -f gmail_connection.yaml
```

## Set Credentials

### Draft environment
```bash
orchestrate connections set-credentials   --app-id gmail_connection   --env draft   -e 'GMAIL_USER=your-email@gmail.com'   -e 'GMAIL_APP_PASSWORD=your-app-password'
```

### Live environment
```bash
orchestrate connections set-credentials   --app-id gmail_connection   --env live   -e 'GMAIL_USER=your-email@gmail.com'   -e 'GMAIL_APP_PASSWORD=your-app-password'
```

## Verify the Connection
```bash
orchestrate connections list
```

# i-oic-wxo-multichannel-integration

## Integrating Conversations Across Facebook

## Overview

### Step 1.	Creating a Facebook Application
To begin integrating your agent with Facebook Messenger, you first need to create a Facebook application. Following these steps:
•	Go to the Facebook for Developers portal and sign in with your Facebook credentials. 
•	From the right-hand menu, open the Apps section.

![facebook_developer](img/facebook_developer.png)
 
•	Click Create App to start the setup process.

![facebook_createapp](img/facebook_createapp.png)

![facebook_createapp](img/facebook_createapp_form.png)
 
•	Under the Business tab, select Business as the app type.
![facebook_bizapp](img/facebook_bizapp.png)


 
•	Click Create app to generate your new Facebook application.
•	Once created, open your app and navigate to App Settings → Basic.
•	Under App Secret, click Show to reveal your Application Secret key.
![facebook_appsecret](img/facebook_appsecret.png)

 


•	Copy the App Secret from above into in Watsonx  orchestrate

### Step 2.	Connecting to a Facebook Page
After creating your Facebook application, the next step is to connect it to your Facebook Page. This allows your agent to send and receive messages through Messenger. Follow these steps:
•	Open your Facebook App in the Facebook for Developers portal.
•	Click Add Product, then select the Messenger tile and click Set Up.

![facebook_dashboard](img/facebook_dashboard.png)
 
•	In the Messenger Settings, scroll down to the Access Tokens section.
•	Under Page Access Tokens, click Connect to link your Facebook Page to the app.
•	Click Generate to create a new Page Access Token.
•	Copy and securely store this token - you’ll need it later to complete the Messenger integration.

![facebook_generate_token](img/facebook_generate_token.png)

 
•	Add Pages(Bottom Blue button on above image) and choose in the current page you want to choose as shown below image.
![facebook_pages](img/facebook_pages.png)

 
### Step 3.	Connecting to Facebook Webhooks
Once your Facebook Page is connected, the next step is to configure webhooks so that Facebook Messenger can communicate with your agent in real time. Follow these steps:
•	In your Facebook App, go to the Messenger Settings page and scroll down to Configure Webhooks.

•	In the Callback URL field, enter the callback URL generated during your integration setup.
•	In the Verify Token field, paste the verify token that was created when you linked your Facebook Page.
•	Click Verify and Save to confirm the connection.

![facebook_apisetup](img/facebook_apisetup.png)

 
Once Callback URLs and verify token have been enabled, make sure to enable toggle buttons for messages and messages_postbacks options.

![facebook_apisetup_part2](img/facebook_apisetup_part2.png)

 
•	To add message subscriptions, click Add Subscriptions.
•	In the Edit Page Subscriptions section, under Subscriptions, select messages and messaging_postbacks.
•	Click Save to finalize your webhook configuration.

![facebook_apisetup_subs](img/facebook_apisetup_subs.png)

Once Page subscriptions added make sure those are visible in the Webhook Subscription

![facebook_webhook](img/facebook_webhook.png)



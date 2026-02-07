export const APP_CONFIG = {
  okta: {
    domain: process.env.NEXT_PUBLIC_OKTA_BASE_URL,
    clientId: process.env.NEXT_PUBLIC_SPA_CLIENT_ID,
  },
  orchestrate: {
    orchestrationID: process.env.NEXT_PUBLIC_ORCHESTRATE_ORCHESTRATIONID,
    hostURL: process.env.NEXT_PUBLIC_ORCHESTRATE_HOSTURL,
    crn: process.env.NEXT_PUBLIC_ORCHESTRATE_CRN,
    agentId: process.env.NEXT_PUBLIC_ORCHESTRATE_AGENT_ID,
    agentEnvironmentId: process.env.NEXT_PUBLIC_ORCHESTRATE_AGENT_ENVIRONMENT_ID,
    clientPrivateKey: process.env.NEXT_PUBLIC_CLIENT_PRIVATE_KEY.replace(/\\n/g, '\n'),
    ibmPublickey: process.env.NEXT_PUBLIC_IBM_PUBLIC_KEY.replace(/\\n/g, '\n')

  },
};
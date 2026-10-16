export default function handler(_request, response) {
  response.setHeader("Cache-Control", "no-store");
  response.status(200).json({
    apiBaseUrl: process.env.API_BASE_URL || "http://localhost:8000",
    authMode: process.env.AUTH_MODE || "firebase",
    firebase: {
      apiKey: process.env.FIREBASE_WEB_API_KEY || "",
      authDomain: process.env.FIREBASE_AUTH_DOMAIN || "",
      projectId: process.env.FIREBASE_PROJECT_ID || "",
      appId: process.env.FIREBASE_APP_ID || ""
    }
  });
}

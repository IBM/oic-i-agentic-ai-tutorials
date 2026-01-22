export const metadata = {
  title: "Embedchat UI",
  description: "Watson Orchestrate Secure Embed with Okta"
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, padding: 0 }}>
        {children}
      </body>
    </html>
  );
}

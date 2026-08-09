import React from "react";
import ReactDOM from "react-dom/client";
import App from "./app/App";
import { AuthorizationProvider } from "./shared/auth/authorization-context";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AuthorizationProvider>
      <App />
    </AuthorizationProvider>
  </React.StrictMode>,
);

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./app/App";
import { AuthorizationProvider } from "./shared/auth/authorization-context";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthorizationProvider>
        <App />
      </AuthorizationProvider>
    </BrowserRouter>
  </React.StrictMode>,
);

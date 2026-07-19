import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { bootstrapTenantFromMe } from "./api/client";
import "./styles.css";

async function boot() {
  await bootstrapTenantFromMe();
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

void boot();

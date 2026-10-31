import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { prepareWebDevelopmentContext } from "./api/webDevSession";
import "./styles.css";

async function boot() {
  await prepareWebDevelopmentContext();
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

void boot();

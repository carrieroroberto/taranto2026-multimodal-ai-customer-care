import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App.jsx";
import { faviconUrl } from "./assets/index.js";
import "./styles.css";

const faviconLink = document.querySelector("link[rel='icon']") || document.createElement("link");
faviconLink.rel = "icon";
faviconLink.type = "image/png";
faviconLink.href = faviconUrl;
document.head.appendChild(faviconLink);

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

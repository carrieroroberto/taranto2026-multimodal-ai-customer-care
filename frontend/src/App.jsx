import { ChatPage } from "./pages/ChatPage.jsx";
import { OperatorDashboardPage } from "./pages/OperatorDashboardPage.jsx";

export default function App() {
  if (window.location.pathname.startsWith("/operator")) {
    return <OperatorDashboardPage />;
  }

  return <ChatPage />;
}

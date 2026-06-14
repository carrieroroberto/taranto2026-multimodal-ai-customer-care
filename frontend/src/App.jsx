import { ChatPage } from "./pages/ChatPage.jsx";
import { KnowledgeBaseAdminPage } from "./pages/KnowledgeBaseAdminPage.jsx";
import { OperatorDashboardPage } from "./pages/OperatorDashboardPage.jsx";

export default function App() {
  if (window.location.pathname.startsWith("/knowledge")) {
    return <KnowledgeBaseAdminPage />;
  }

  if (window.location.pathname.startsWith("/operator")) {
    return <OperatorDashboardPage />;
  }

  return <ChatPage />;
}

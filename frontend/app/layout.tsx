import "./globals.css";
import type { Metadata } from "next";
import { SubjectProvider } from "@/components/SubjectContext";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  title: "ExamMind — AI exam prep",
  description: "Ask your notes, predict hot topics, practise and get graded.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <SubjectProvider>
          <Shell>{children}</Shell>
        </SubjectProvider>
      </body>
    </html>
  );
}

import { motion } from "framer-motion";
import { Bot, User } from "lucide-react";
import { Fragment } from "react";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}

const URL_PATTERN = /(https?:\/\/[^\s]+)/g;

const renderContentWithLinks = (content: string) => {
  const lines = content.split("\n");

  return lines.map((line, lineIndex) => {
    const parts = line.split(URL_PATTERN);

    return (
      <Fragment key={`${line}-${lineIndex}`}>
        {parts.map((part, partIndex) => {
          if (/^https?:\/\/[^\s]+$/.test(part)) {
            return (
              <a
                key={`${part}-${partIndex}`}
                href={part}
                target="_blank"
                rel="noreferrer"
                className="break-all text-sky-700 underline underline-offset-2 transition-colors hover:text-sky-900"
              >
                {part}
              </a>
            );
          }

          return <Fragment key={`${part}-${partIndex}`}>{part}</Fragment>;
        })}
        {lineIndex < lines.length - 1 ? <br /> : null}
      </Fragment>
    );
  });
};

const ChatMessage = ({ role, content, timestamp }: ChatMessageProps) => {
  const isUser = role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`flex w-full ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div className={`flex w-full max-w-4xl gap-3 ${isUser ? "max-w-2xl flex-row-reverse" : ""}`}>
        <div
          className={`mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl shadow-sm ${
            isUser ? "gradient-primary" : "gradient-secondary"
          }`}
        >
          {isUser ? (
            <User className="h-4 w-4 text-primary-foreground" />
          ) : (
            <Bot className="h-4 w-4 text-secondary-foreground" />
          )}
        </div>
        <div className={`flex-1 space-y-2 ${isUser ? "items-end text-right" : ""}`}>
          <div className={`flex items-center gap-2 ${isUser ? "justify-end" : ""}`}>
            <span className="text-sm font-semibold font-display text-slate-900">
              {isUser ? "Vous" : "UniBot"}
            </span>
            {timestamp && (
              <span className="text-xs text-slate-500">{timestamp}</span>
            )}
          </div>
          <div
            className={`inline-block max-w-full whitespace-pre-wrap rounded-[1.35rem] border px-4 py-3 text-sm leading-7 shadow-sm ${
              isUser
                ? "border-orange-200 bg-orange-50/95 text-slate-900"
                : "border-sky-100 bg-white/95 text-slate-900"
            }`}
          >
            {renderContentWithLinks(content)}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default ChatMessage;

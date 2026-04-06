import { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";
import { motion } from "framer-motion";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
}

const ChatInput = ({ onSend, isLoading }: ChatInputProps) => {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + "px";
    }
  }, [input]);

  const handleSubmit = () => {
    if (!input.trim() || isLoading) return;
    onSend(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t border-slate-200/70 bg-white/80 px-3 py-4 backdrop-blur sm:px-5 lg:px-8">
      <div className="mx-auto max-w-5xl">
        <div className="relative rounded-[1.75rem] border border-slate-200 bg-white/95 p-2 shadow-[0_16px_40px_-24px_rgba(15,23,42,0.35)]">
          <div className="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-orange-200/70 to-transparent" />
          <div className="relative flex items-end rounded-[1.2rem] bg-slate-50/85 transition-shadow focus-within:ring-2 focus-within:ring-orange-200/70">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Posez votre question sur l'emploi du temps..."
              rows={1}
              className="flex-1 resize-none bg-transparent px-4 py-3.5 text-sm text-foreground placeholder:text-slate-500 focus:outline-none"
            />
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={handleSubmit}
              disabled={!input.trim() || isLoading}
              className="m-2 flex h-10 w-10 items-center justify-center rounded-2xl gradient-primary text-primary-foreground shadow-sm transition-opacity disabled:opacity-40"
            >
              <Send className="h-4 w-4" />
            </motion.button>
          </div>
        </div>
        <div className="mt-2 flex flex-col items-center justify-between gap-2 px-1 text-xs text-slate-500 sm:flex-row">
          <p>Entrée pour envoyer, Maj + Entrée pour une nouvelle ligne.</p>
          <p>Vérifiez les informations importantes avant décision.</p>
        </div>
      </div>
    </div>
  );
};

export default ChatInput;

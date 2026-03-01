const TypingIndicator = () => (
  <div className="flex gap-3 bg-chat-ai px-4 py-6">
    <div className="mx-auto flex w-full max-w-3xl gap-4">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg gradient-secondary">
        <svg className="h-4 w-4 text-secondary-foreground" viewBox="0 0 24 24" fill="currentColor">
          <circle cx="12" cy="12" r="3" />
        </svg>
      </div>
      <div className="flex items-center gap-1.5 pt-2">
        <span className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-pulse-dot" />
        <span className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-pulse-dot [animation-delay:0.2s]" />
        <span className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-pulse-dot [animation-delay:0.4s]" />
      </div>
    </div>
  </div>
);

export default TypingIndicator;

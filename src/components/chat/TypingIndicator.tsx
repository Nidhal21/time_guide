const TypingIndicator = () => (
  <div className="flex w-full justify-start">
    <div className="flex w-full max-w-4xl gap-3">
      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl gradient-secondary shadow-sm">
        <svg className="h-4 w-4 text-secondary-foreground" viewBox="0 0 24 24" fill="currentColor">
          <circle cx="12" cy="12" r="3" />
        </svg>
      </div>
      <div className="rounded-[1.35rem] border border-sky-100 bg-white/95 px-4 py-4 shadow-sm">
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-pulse-dot" />
          <span className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-pulse-dot [animation-delay:0.2s]" />
          <span className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-pulse-dot [animation-delay:0.4s]" />
        </div>
      </div>
    </div>
  </div>
);

export default TypingIndicator;

import { motion } from "framer-motion";
import { Newspaper, CalendarDays, DoorOpen, BookOpen, GraduationCap } from "lucide-react";

interface WelcomeScreenProps {
  onSuggestionClick: (text: string) => void;
}

const suggestions = [
  {
    icon: Newspaper,
    text: "Quelles sont les dernieres actualites de ENET'Com ?",
  },
  {
    icon: CalendarDays,
    text: "Quel est l'emploi du temps de ma classe aujourd'hui ?",
  },
  {
    icon: DoorOpen,
    text: "Quelles sont les salles disponibles en ce moment ?",
  },
  {
    icon: BookOpen,
    text: "Peux-tu me montrer les plans d'etude ?",
  },
];

const WelcomeScreen = ({ onSuggestionClick }: WelcomeScreenProps) => {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-12">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="mb-8 text-center"
      >
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl gradient-hero shadow-glow-primary">
          <GraduationCap className="h-8 w-8 text-primary-foreground" />
        </div>
        <h1 className="mb-2 font-display text-3xl font-bold text-foreground">
          Enet'Bot
        </h1>
        <p className="text-muted-foreground">
          Votre assistant intelligent pour les emplois du temps ENETCOM
        </p>
      </motion.div>

      <div className="grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-2">
        {suggestions.map((suggestion, i) => (
          <motion.button
            key={i}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.1 * i }}
            whileHover={{ scale: 1.02, y: -2 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onSuggestionClick(suggestion.text)}
            className="flex items-start gap-3 rounded-xl border border-border bg-card p-4 text-left shadow-soft transition-shadow hover:shadow-card"
          >
            <suggestion.icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
            <span className="text-sm text-foreground">{suggestion.text}</span>
          </motion.button>
        ))}
      </div>
    </div>
  );
};

export default WelcomeScreen;

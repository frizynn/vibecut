import { VibecutLogo } from "~/components/ui/VibecutLogo";

export function Footer() {
  return (
    <footer className="w-full border-t border-border/30 bg-background/70 backdrop-blur supports-[backdrop-filter]:bg-background/50">
      <div className="max-w-7xl mx-auto px-6 py-4 flex flex-col md:flex-row items-center justify-between gap-3 text-xs text-muted-foreground">
        <div className="inline-flex items-center gap-2">
          <VibecutLogo className="w-4 h-4" />
          <span>© {new Date().getFullYear()} Vibecut Studio</span>
        </div>
        <nav className="flex flex-wrap items-center gap-4">
          <a
            href="https://github.com/frizynn/vibecut"
            target="_blank"
            rel="noreferrer"
            className="hover:text-foreground">
            Docs
          </a>
          <a href="/privacy" className="hover:text-foreground">
            Privacy
          </a>
          <a href="/terms" className="hover:text-foreground">
            Terms
          </a>
          <a href="/marketplace" className="hover:text-foreground">
            Marketplace
          </a>
          <a href="/roadmap" className="hover:text-foreground">
            Roadmap
          </a>
          <a
            href="https://github.com/frizynn/vibecut"
            target="_blank"
            rel="noreferrer"
            className="hover:text-foreground">
            GitHub
          </a>
          <a href="https://discord.gg/24Mt5DGcbx" target="_blank" rel="noreferrer" className="hover:text-foreground">
            Discord
          </a>
          <a href="https://github.com/frizynn/vibecut" target="_blank" rel="noreferrer" className="hover:text-foreground">
            Twitter
          </a>
        </nav>
      </div>
    </footer>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Hand, Menu, Moon, Sun, X } from "lucide-react";
import { useEffect, useState } from "react";

const navigation = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/translator/sign-to-speech", label: "Translator" },
  { href: "/history", label: "History" },
  { href: "/profile", label: "Profile" },
  { href: "/settings", label: "Settings" },
  { href: "/about", label: "About" }
];

type Theme = "light" | "dark";

export function SiteHeader() {
  const pathname = usePathname();
  const [theme, setTheme] = useState<Theme>("light");
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  function toggleTheme() {
    const nextTheme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
  }

  return (
    <header className="site-header">
      <div className="header-inner">
        <Link aria-label="SignLingo home" className="brand" href="/">
          <span className="brand-mark" aria-hidden="true">
            <Hand />
          </span>
          SignLingo
        </Link>
        <nav aria-label="Main navigation" className="desktop-nav">
          {navigation.map((item) => (
            <Link
              aria-current={pathname === item.href ? "page" : undefined}
              className="header-link"
              href={item.href}
              key={item.href}
              onClick={() => setMenuOpen(false)}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="header-actions">
          <Link className="header-link header-signin" href="/login">
            Sign in
          </Link>
          <button
            aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
            className="icon-button"
            onClick={toggleTheme}
            type="button"
          >
            {theme === "light" ? <Moon aria-hidden="true" /> : <Sun aria-hidden="true" />}
          </button>
          <Link className="button header-cta" href="/translator/sign-to-speech">
            Start translating
          </Link>
          <button
            aria-expanded={menuOpen}
            aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
            className="mobile-menu-button"
            onClick={() => setMenuOpen((open) => !open)}
            type="button"
          >
            {menuOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
          </button>
        </div>
      </div>
      <nav
        aria-label="Mobile navigation"
        className="mobile-nav"
        data-open={menuOpen}
        hidden={!menuOpen}
      >
        {navigation.map((item) => (
          <Link
            aria-current={pathname === item.href ? "page" : undefined}
            href={item.href}
            key={item.href}
          >
            {item.label}
          </Link>
        ))}
        <Link href="/profile" onClick={() => setMenuOpen(false)}>
          Profile
        </Link>
        <Link href="/settings" onClick={() => setMenuOpen(false)}>
          Settings
        </Link>
        <Link href="/login" onClick={() => setMenuOpen(false)}>
          Sign in
        </Link>
      </nav>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <p>SignLingo · Built with accessibility and respect for ISL in mind.</p>
        <nav aria-label="Footer navigation" className="footer-links">
          <Link className="footer-link" href="/about">
            About
          </Link>
          <Link className="footer-link" href="/settings">
            Preferences
          </Link>
        </nav>
      </div>
    </footer>
  );
}

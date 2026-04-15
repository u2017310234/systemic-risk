import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        bg: "#06131f",
        panel: "#0b1d2c",
        panelAlt: "#10263a",
        line: "#1c3851",
        text: "#eff7ff",
        muted: "#8ea7bc",
        accent: "#f4b860",
        cool: "#4ab8d9",
        danger: "#ff7a59"
      },
      fontFamily: {
        display: ["Georgia", "Times New Roman", "serif"],
        sans: ["IBM Plex Sans", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular", "monospace"]
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(244,184,96,0.08), 0 24px 60px rgba(2,10,16,0.45)"
      },
      backgroundImage: {
        mesh:
          "radial-gradient(circle at top left, rgba(244,184,96,0.10), transparent 28%), radial-gradient(circle at 85% 15%, rgba(74,184,217,0.10), transparent 20%), linear-gradient(180deg, rgba(9,23,35,0.98), rgba(4,11,18,1))"
      }
    }
  },
  plugins: []
};

export default config;

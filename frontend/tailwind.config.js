/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#14213d",
        paper: "#f7f7f2",
        mint: "#2a9d8f",
        coral: "#e76f51",
        amber: "#e9c46a"
      }
    }
  },
  plugins: []
};


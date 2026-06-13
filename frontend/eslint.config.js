import react from "eslint-plugin-react";

export default [
  {
    ignores: [
      "dist/**",
      "node_modules/**",
      "src/**/*.ts",
      "src/**/*.tsx",
      "src/**/* copy*.jsx",
      "src/**/* copy*.js"
    ]
  },
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: {
          jsx: true
        }
      },
      globals: {
        console: "readonly",
        document: "readonly",
        event: "readonly",
        FormData: "readonly",
        localStorage: "readonly",
        setTimeout: "readonly",
        WebSocket: "readonly",
        window: "readonly"
      }
    },
    plugins: {
      react
    },
    rules: {
      ...react.configs.recommended.rules,
      "react/no-unknown-property": "off",
      "react/prop-types": "off",
      "react/react-in-jsx-scope": "off"
    },
    settings: {
      react: {
        version: "detect"
      }
    }
  }
];

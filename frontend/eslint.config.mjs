import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  // Allow underscore-prefixed unused variables (common pattern for ignored parameters)
  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
        },
      ],
    },
  },
  // 3D scene adapted from Agent Office 3D (MIT): React Three Fiber code mutates
  // three.js objects and refs inside useFrame and builds geometry with random
  // variation on mount. Those are the normal R3F patterns, which the React
  // Compiler rules flag; they stay off only for the scene files.
  {
    files: [
      "src/components/oficina3d/escena/**",
      "src/components/oficina3d/entornos/*.tsx",
      "src/components/oficina3d/Escena3D.tsx",
    ],
    rules: {
      "react-hooks/refs": "off",
      "react-hooks/immutability": "off",
      "react-hooks/purity": "off",
      "react-hooks/set-state-in-effect": "off",
    },
  },
]);

export default eslintConfig;

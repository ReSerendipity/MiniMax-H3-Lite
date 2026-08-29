// 最小 ESLint flat 配置：语法级解析（tests 内 require/import 混用，module 模式两者均可解析）。
// 规则集待专项决策后补充；flake8 是本仓的主力 lint 门禁。
export default [
  {
    files: ["tests/**/*.js"],
    languageOptions: { ecmaVersion: "latest", sourceType: "module" },
  },
];

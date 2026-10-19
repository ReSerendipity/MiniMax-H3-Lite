// 最小 ESLint flat 配置：语法级解析（tests 内 require/import 混用，module 模式两者均可解析）。
// 规则集待专项决策后补充；flake8 是本仓的主力 lint 门禁。
// 2026-09-05：files 纳入 assets/**/*.js —— 业务前端脚本（assets/js/shared.js，
// 1268 行）此前游离于静态检查外（前端工程体系评估反模式 #3），现已纳入。
export default [
  {
    files: ["tests/**/*.js", "assets/**/*.js"],
    languageOptions: { ecmaVersion: "latest", sourceType: "module" },
  },
];

/// <reference types="vite/client" />

// CSS Modulesの型定義
declare module '*.module.css' {
  const classes: { [key: string]: string };
  export default classes;
}

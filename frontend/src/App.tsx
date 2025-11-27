/**
 * App.tsx
 * DualEditorコンポーネントのデモアプリケーション
 */

import React from 'react';
import DualEditor from './components/DualEditor';
import './App.css';

const App: React.FC = () => {
  return (
    <div className="App">
      <DualEditor />
    </div>
  );
};

export default App;

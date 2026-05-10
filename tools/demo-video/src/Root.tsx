import React from 'react';
import {Composition} from 'remotion';
import {TerminalDemo} from './TerminalDemo';

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="AsmCliDemo"
      component={TerminalDemo}
      durationInFrames={900}
      fps={30}
      width={1280}
      height={720}
    />
  );
};

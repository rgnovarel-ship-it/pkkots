import React from "react";
import { Composition } from "remotion";
import { PinNovarel } from "./pin/PinNovarel";
import { DURATION, FPS } from "./pin/timing";
import { LAYOUT } from "./pin/tokens";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="PinNovarel"
      component={PinNovarel}
      durationInFrames={DURATION}
      fps={FPS}
      width={LAYOUT.width}
      height={LAYOUT.height}
    />
  );
};

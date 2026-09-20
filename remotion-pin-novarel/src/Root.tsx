import React from "react";
import { Composition } from "remotion";
import { LAYOUT } from "./brand";
import { PubNovarel } from "./pub/PubNovarel";
import { DURATION as PUB_DURATION, FPS as PUB_FPS } from "./pub/timing";
import { PinNovarel } from "./pin/PinNovarel";
import { DURATION as PIN_DURATION, FPS as PIN_FPS } from "./pin/timing";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* Version courante : pub en lumière naturelle, monde clair du site */}
      <Composition
        id="PubNovarel"
        component={PubNovarel}
        durationInFrames={PUB_DURATION}
        fps={PUB_FPS}
        width={LAYOUT.width}
        height={LAYOUT.height}
      />
      {/* Première version, gardée en archive : scène de nuit */}
      <Composition
        id="PinNovarel"
        component={PinNovarel}
        durationInFrames={PIN_DURATION}
        fps={PIN_FPS}
        width={LAYOUT.width}
        height={LAYOUT.height}
      />
    </>
  );
};

/**
 * Note : les API Node.JS n'utilisent pas ce fichier de config.
 * https://remotion.dev/docs/config
 */

import { Config } from "@remotion/cli/config";

Config.setRspack(true);
// PNG en frame intermédiaire : sortie en yuv420p (le JPEG force yuvj420p)
Config.setVideoImageFormat("png");
Config.setOverwriteOutput(true);
Config.setCodec("h264");
Config.setPixelFormat("yuv420p");
Config.setCrf(18);

// Le rendu a besoin d'un Chromium. `npx remotion browser ensure` en installe un ;
// si un Chromium est déjà présent sur la machine, on peut le pointer ici :
// Config.setBrowserExecutable("/chemin/vers/chromium");
const localChromium = process.env.REMOTION_BROWSER_EXECUTABLE;
if (localChromium) {
  Config.setBrowserExecutable(localChromium);
}

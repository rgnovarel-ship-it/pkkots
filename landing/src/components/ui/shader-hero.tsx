import { useEffect, useRef, type ReactNode } from "react";

/* ==========================================================================
   Shader Hero — fond WebGL « relevé topographique ».
   Volontairement monochrome (encre + olive) : le vert signal est réservé
   au meilleur choix, au bouton d'action et à l'icône d'alerte.
   Le shader est un décor : il reste sous le texte, jamais devant.
   ========================================================================== */

const VERT = `#version 300 es
in vec2 a_pos;
void main() { gl_Position = vec4(a_pos, 0.0, 1.0); }
`;

const FRAG = `#version 300 es
precision highp float;
out vec4 fragColor;

uniform vec2  u_res;
uniform float u_time;

/* Les trois valeurs sombres de NOVAREL. Aucune autre teinte n'entre ici. */
const vec3 BASE  = vec3(0.047, 0.055, 0.043); /* #0c0e0b */
const vec3 LINE  = vec3(0.161, 0.180, 0.133); /* #292e22 */
const vec3 EDGE  = vec3(0.231, 0.255, 0.196); /* #3b4132 */

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
             mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p *= 2.03;
    a *= 0.5;
  }
  return v;
}

void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 p = uv;
  p.x *= u_res.x / u_res.y;

  /* Dérive très lente : le relief respire, il ne bouge pas. */
  float t = u_time * 0.012;
  float field = fbm(p * 2.1 + vec2(t, t * 0.35));
  field += 0.22 * fbm(p * 4.6 - vec2(t * 0.6, 0.0));

  /* Courbes de niveau : on découpe le champ en bandes fines. */
  float bands = field * 11.0;
  float d = abs(fract(bands) - 0.5);
  float w = fwidth(bands) * 1.4;
  float contour = 1.0 - smoothstep(0.0, max(w, 0.012), d - 0.06);

  /* Le relevé s'efface vers le bas et vers la gauche :
     le titre se pose sur une zone calme. */
  float calm = smoothstep(0.0, 0.85, uv.x) * 0.75 + 0.25;
  calm *= smoothstep(-0.1, 0.55, uv.y);

  vec3 col = BASE;
  col = mix(col, LINE, contour * 0.55 * calm);
  col = mix(col, EDGE, contour * smoothstep(0.55, 0.95, field) * 0.5 * calm);

  /* Vignette + léger grain pour casser le dégradé trop propre. */
  vec2 v = uv - 0.5;
  col *= 1.0 - dot(v, v) * 0.55;
  col += (hash(gl_FragCoord.xy + u_time) - 0.5) * 0.012;

  fragColor = vec4(col, 1.0);
}
`;

function compile(gl: WebGL2RenderingContext, type: number, src: string) {
  const sh = gl.createShader(type)!;
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    console.warn("[shader-hero]", gl.getShaderInfoLog(sh));
    gl.deleteShader(sh);
    return null;
  }
  return sh;
}

function ShaderCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl2", {
      antialias: false,
      alpha: false,
      powerPreference: "low-power",
    });
    // Pas de WebGL2 : on garde le fond uni du hero, la page reste intacte.
    if (!gl) return;

    const vs = compile(gl, gl.VERTEX_SHADER, VERT);
    const fs = compile(gl, gl.FRAGMENT_SHADER, FRAG);
    if (!vs || !fs) return;

    const prog = gl.createProgram()!;
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      console.warn("[shader-hero]", gl.getProgramInfoLog(prog));
      return;
    }
    gl.useProgram(prog);

    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 3, -1, -1, 3]),
      gl.STATIC_DRAW,
    );
    const loc = gl.getAttribLocation(prog, "a_pos");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

    const uRes = gl.getUniformLocation(prog, "u_res");
    const uTime = gl.getUniformLocation(prog, "u_time");

    // Plafonné à 1.5 : un shader plein écran en DPR 3 chauffe pour rien.
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    const resize = () => {
      const { clientWidth: w, clientHeight: h } = canvas;
      canvas.width = Math.max(1, Math.round(w * dpr));
      canvas.height = Math.max(1, Math.round(h * dpr));
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(uRes, canvas.width, canvas.height);
    };
    resize();

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const draw = (t: number) => {
      gl.uniform1f(uTime, t);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    };

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    let raf = 0;
    let visible = true;
    const start = performance.now();

    const loop = () => {
      draw((performance.now() - start) / 1000);
      raf = requestAnimationFrame(loop);
    };

    const run = () => {
      cancelAnimationFrame(raf);
      // Mouvement réduit ou hero hors écran : une seule image, puis on arrête.
      if (reduced.matches || !visible) {
        draw(12);
        return;
      }
      loop();
    };

    const io = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
        run();
      },
      { threshold: 0 },
    );
    io.observe(canvas);

    reduced.addEventListener("change", run);
    run();

    return () => {
      cancelAnimationFrame(raf);
      reduced.removeEventListener("change", run);
      io.disconnect();
      ro.disconnect();
      gl.deleteProgram(prog);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
      gl.deleteBuffer(buf);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden="true"
      className="absolute inset-0 h-full w-full"
    />
  );
}

export function ShaderHero({ children }: { children: ReactNode }) {
  return (
    <section className="relative isolate overflow-hidden bg-night-paper">
      <ShaderCanvas />
      {/* Le voile garantit le contraste du titre quoi que fasse le shader. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-gradient-to-r from-night-paper via-night-paper/80 to-night-paper/30"
      />
      <div
        aria-hidden="true"
        className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-b from-transparent to-night-paper"
      />
      <div className="relative">{children}</div>
    </section>
  );
}

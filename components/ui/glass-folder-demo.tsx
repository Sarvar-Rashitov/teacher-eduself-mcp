"use client"

import GlassFolder from "@/components/ui/glass-folder-cards"

/**
 * Three folders on a dotted desk: milk glass over a long-exposure print with a
 * key that adds files, a plain archive with a menu, and smoked glass over red
 * ink. Hover one to lean its glass toward you, click it to open it.
 */
export default function GlassFolderCardsDemo() {
  return (
    <div
      className="relative flex w-full flex-col items-center justify-center overflow-hidden bg-background px-6 py-16"
      style={{ minHeight: "100svh" }}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 text-foreground opacity-[0.13]"
        style={{
          backgroundImage: "radial-gradient(currentColor 1.1px, transparent 1.4px)",
          backgroundSize: "22px 22px",
        }}
      />
      <div className="relative grid max-w-[1180px] grid-cols-1 items-end justify-items-center gap-x-14 gap-y-10 md:grid-cols-2 xl:grid-cols-3">
        <GlassFolder
          label="Fanlar Kutubxonasi"
          art="eduplay"
          seed={3}
          appearDelay={0}
          files={[
            { name: "Umumiy", meta: "Barcha testlar", art: "eduplay" },
            { name: "Fizika", meta: "Zichlik, Massa", art: "physics" },
            { name: "Matematika", meta: "Oddiy kasrlar", art: "math" },
            { name: "Informatika", meta: "Algoritmlar", art: "aurora" },
            { name: "Biologiya", meta: "Hujayra tuzilishi", art: "biology" },
          ]}
        />
        <GlassFolder
          label="Arxiv Fanlar"
          art="none"
          action="more"
          labelPlacement="top-left"
          appearDelay={140}
          files={[
            { name: "Kimyo 2024", meta: "38 test", art: "dusk" },
            { name: "Tarix", meta: "12 viktorina" },
            { name: "Ingliz Tili", meta: "Grammar · 20 test", art: "ember" },
            { name: "Geografiya", meta: "8 test" },
          ]}
          menu={[{ label: "Nomini o‘zgartirish" }, { label: "Ulashish…" }, { label: "Arxivga o‘tkazish", danger: true }]}
        />
        <GlassFolder
          label="Mening Testlarim"
          meta="Bugun faol"
          tone="dark"
          art="ember"
          seed={11}
          action="none"
          labelPlacement="top-right"
          appearDelay={280}
          files={[
            { name: "7-sinf Nazorat", meta: "64 savol", art: "verdant" },
            { name: "Choraklik test", meta: "TXT · 4 KB" },
            { name: "Olimpiada v3", meta: "DRX · 18 MB", art: "aurora" },
          ]}
        />
      </div>
      <p className="relative mt-14 font-mono text-[11px] tracking-[0.18em] text-muted-foreground uppercase">
        Hover to lean · Click to open · + to add
      </p>
    </div>
  )
}

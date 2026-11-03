import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronRight,
  LayoutDashboard,
  GraduationCap,
  Sparkles,
  Trophy,
  Settings,
  LogOut,
  X
} from "lucide-react";

/**
 * ArcSidebar Component
 * 
 * High-performance animated sidebar featuring a seamless SVG quadratic Bézier arc edge,
 * spring physics transitions, and zero background click interception when collapsed.
 */
export const ArcSidebar = ({
  isOpen: controlledIsOpen,
  onToggle,
  children
}) => {
  const [internalIsOpen, setInternalIsOpen] = useState(false);
  const isControlled = controlledIsOpen !== undefined;
  const isOpen = isControlled ? controlledIsOpen : internalIsOpen;

  const handleToggle = () => {
    if (isControlled && onToggle) {
      onToggle(!isOpen);
    } else {
      setInternalIsOpen((prev) => !prev);
    }
  };

  // Close on Escape key press when open
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && isOpen) {
        if (isControlled && onToggle) {
          onToggle(false);
        } else {
          setInternalIsOpen(false);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isControlled, onToggle]);

  return (
    <>
      {/* Optional Soft Backdrop when open */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={handleToggle}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]"
            aria-hidden="true"
          />
        )}
      </AnimatePresence>

      {/* Main Sliding Wrapper: pointer-events-none ensures no dashboard click blockage */}
      <motion.aside
        initial={false}
        animate={{ x: isOpen ? 0 : -280 }}
        transition={{ type: "spring", stiffness: 340, damping: 32 }}
        className="fixed top-0 left-0 h-full z-50 flex pointer-events-none select-none"
        aria-label="Navigation Sidebar"
      >
        {/* 1. Rectangular 280px Body Container */}
        <div
          className="w-[280px] h-full flex flex-col justify-between pointer-events-auto bg-[#0a0d14] text-white border-r border-white/5 shadow-2xl relative z-10"
          style={{
            background: "var(--sidebar-bg, #0b0f19)",
          }}
        >
          {/* Header Section */}
          <div className="p-6 border-b border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#FF7527] to-[#E04D00] flex items-center justify-center font-bold text-white shadow-md shadow-orange-500/20">
                E
              </div>
              <div>
                <span className="font-extrabold text-base tracking-tight text-white block">
                  Edu<span className="text-[#FF7527]">Self</span>
                </span>
                <span className="text-[10px] font-mono tracking-wider text-white/50 block">
                  TEACHER NODE
                </span>
              </div>
            </div>
            {isOpen && (
              <button
                type="button"
                onClick={handleToggle}
                className="md:hidden text-white/60 hover:text-white p-1"
                aria-label="Close sidebar"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Body Section / Dynamic Placeholder */}
          <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
            {children ? (
              children
            ) : (
              <>
                {/* Sidebar Content Goes Here: Navigation Items */}
                <div className="space-y-1">
                  <span className="px-3 text-[10px] font-mono uppercase tracking-wider text-white/40">
                    Boshqaruv
                  </span>
                  <a
                    href="#dashboard"
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold bg-white/10 text-white shadow-sm"
                  >
                    <LayoutDashboard className="w-4 h-4 text-[#FF7527]" />
                    <span>Dashboard</span>
                  </a>
                  <a
                    href="#quizzes"
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-white/70 hover:bg-white/5 hover:text-white transition-colors"
                  >
                    <GraduationCap className="w-4 h-4 text-[#38BDF8]" />
                    <span>Viktorinalar</span>
                  </a>
                  <a
                    href="#ai-workspace"
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-white/70 hover:bg-white/5 hover:text-white transition-colors"
                  >
                    <Sparkles className="w-4 h-4 text-[#FBBF24]" />
                    <span>AI Generator</span>
                  </a>
                  <a
                    href="#leaderboard"
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-white/70 hover:bg-white/5 hover:text-white transition-colors"
                  >
                    <Trophy className="w-4 h-4 text-[#A78BFA]" />
                    <span>Leaderboard</span>
                  </a>
                </div>

                {/* Secondary Section */}
                <div className="space-y-1 pt-4 border-t border-white/5">
                  <span className="px-3 text-[10px] font-mono uppercase tracking-wider text-white/40">
                    Tizim
                  </span>
                  <a
                    href="#settings"
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-white/70 hover:bg-white/5 hover:text-white transition-colors"
                  >
                    <Settings className="w-4 h-4 text-white/50" />
                    <span>Sozlamalar</span>
                  </a>
                </div>
              </>
            )}
          </div>

          {/* Footer User Info */}
          <div className="p-4 border-t border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-white/10 border border-white/20 flex items-center justify-center font-bold text-xs text-[#FF7527]">
                DK
              </div>
              <div className="truncate">
                <span className="text-xs font-bold text-white block truncate">
                  Dilshod Karimov
                </span>
                <span className="text-[10px] text-white/40 block truncate">
                  ustoz@maktab.uz
                </span>
              </div>
            </div>
            <button
              type="button"
              className="text-white/40 hover:text-red-400 p-1.5 rounded-lg hover:bg-white/5 transition-colors"
              title="Chiqish"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 2. Outward SVG Quadratic Bézier Arc Edge (-1px overlap to prevent Retina seams) */}
        <div className="relative h-full pointer-events-auto">
          <svg
            className="h-full w-[48px] -ml-[1px] block select-none pointer-events-auto filter drop-shadow-[8px_0_16px_rgba(0,0,0,0.35)]"
            viewBox="0 0 100 1000"
            preserveAspectRatio="none"
            shapeRendering="geometricPrecision"
          >
            {/* Filled outward arc body matching sidebar background */}
            <motion.path
              d={
                isOpen
                  ? "M 0,0 Q 100,500 0,1000 L 0,1000 L 0,0 Z"
                  : "M 0,0 Q 95,500 0,1000 L 0,1000 L 0,0 Z"
              }
              fill="var(--sidebar-bg, #0b0f19)"
              transition={{ type: "spring", stiffness: 340, damping: 32 }}
            />
            {/* Subtle outer curved border highlight */}
            <motion.path
              d={
                isOpen
                  ? "M 0,0 Q 100,500 0,1000"
                  : "M 0,0 Q 95,500 0,1000"
              }
              fill="none"
              stroke="var(--sidebar-border, rgba(255,255,255,0.12))"
              strokeWidth="3"
              vectorEffect="non-scaling-stroke"
              transition={{ type: "spring", stiffness: 340, damping: 32 }}
            />
          </svg>

          {/* Toggle Button Positioned directly at the Arc Apex */}
          <button
            type="button"
            onClick={handleToggle}
            aria-expanded={isOpen}
            aria-label="Toggle navigation sidebar"
            className="absolute top-1/2 -translate-y-1/2 left-[28px] -translate-x-1/2 z-20 flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-r from-[#FF7527] to-[#FF8F4D] text-white shadow-lg shadow-orange-500/40 hover:scale-110 active:scale-95 transition-transform duration-150 focus:outline-none focus:ring-2 focus:ring-orange-400 cursor-pointer pointer-events-auto"
          >
            <motion.div
              animate={{ rotate: isOpen ? 180 : 0 }}
              transition={{ type: "spring", stiffness: 340, damping: 25 }}
              className="flex items-center justify-center"
            >
              <ChevronRight className="w-4 h-4 stroke-[2.5]" />
            </motion.div>
          </button>
        </div>
      </motion.aside>
    </>
  );
};

/**
 * DashboardLayoutDemo
 * 
 * Standalone demo wrapper demonstrating a stationary dashboard background layout
 * with the animated ArcSidebar overlaid seamlessly.
 */
export const DashboardLayoutDemo = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <div className="relative min-h-screen w-full bg-[#06080e] text-white overflow-hidden flex flex-col font-sans">
      {/* Animated Arc Sidebar */}
      <ArcSidebar
        isOpen={isSidebarOpen}
        onToggle={setIsSidebarOpen}
      />

      {/* Stationary Dashboard Background & Main Surface */}
      <div className="flex-1 flex flex-col pl-16 pr-6 py-6 md:pl-20 md:pr-10 max-w-7xl mx-auto w-full">
        {/* Top Header Bar */}
        <header className="flex items-center justify-between pb-8 border-b border-white/10">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">
              O‘qituvchi Boshqaruv Markazi
            </h1>
            <p className="text-xs text-white/50 mt-1">
              EduSelf AI va Real-Vaqtli Gamifikatsiya Tizimi
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-xs font-bold hover:bg-white/10 transition-colors"
            >
              Yon Menyu ({isSidebarOpen ? "Ochiq" : "Yopiq"})
            </button>
            <div className="h-9 w-9 rounded-full bg-[#FF7527] flex items-center justify-center font-bold text-sm">
              DK
            </div>
          </div>
        </header>

        {/* Dashboard Stat Bento Grid */}
        <main className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mt-8">
          <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/10">
            <span className="text-[11px] font-mono text-white/40 uppercase">Faol O‘quvchilar</span>
            <h3 className="text-2xl font-extrabold mt-1 text-[#FF7527]">148 nafar</h3>
            <span className="text-[11px] text-emerald-400 mt-2 block font-medium">↑ 12% o‘sish bu hafta</span>
          </div>

          <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/10">
            <span className="text-[11px] font-mono text-white/40 uppercase">O‘tkazilgan O‘yinlar</span>
            <h3 className="text-2xl font-extrabold mt-1 text-[#38BDF8]">34 ta</h3>
            <span className="text-[11px] text-white/50 mt-2 block font-medium">7-8 sinflar bo‘yicha</span>
          </div>

          <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/10">
            <span className="text-[11px] font-mono text-white/40 uppercase">AI Token Qoldig‘i</span>
            <h3 className="text-2xl font-extrabold mt-1 text-[#FBBF24]">864,200</h3>
            <span className="text-[11px] text-white/50 mt-2 block font-medium">1,000,000 oylik limit</span>
          </div>

          <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/10">
            <span className="text-[11px] font-mono text-white/40 uppercase">O‘rtacha Natija</span>
            <h3 className="text-2xl font-extrabold mt-1 text-[#A78BFA]">87.4%</h3>
            <span className="text-[11px] text-emerald-400 mt-2 block font-medium">A’lo o‘zlashtirish</span>
          </div>
        </main>

        {/* Informational Guidance Box */}
        <div className="mt-8 p-6 rounded-2xl bg-gradient-to-r from-orange-500/10 via-transparent to-blue-500/10 border border-white/10">
          <h2 className="text-lg font-bold">ArcSidebar Bilan Tanishing</h2>
          <p className="text-xs text-white/60 mt-1 max-w-2xl leading-relaxed">
            Chap tarafdagi yumaloq <span className="text-[#FF7527] font-semibold">Q 100,500</span> SVG simob yoyi tugmasini bosing yoki klaviaturadagi <kbd className="px-1.5 py-0.5 rounded bg-white/10 text-white font-mono text-[10px]">Escape</kbd> tugmasi orqali menyuni yoping. Menyu yopilganda asosiy oynadagi barcha tugmalar erkin bosiladi.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ArcSidebar;

"use client";

import React from "react";
import { motion } from "framer-motion";
import { ArrowRight, Sparkles } from "lucide-react";
import SpotlightBackground from "@/components/ui/spotlight-background";

export const DemoOne: React.FC = () => {
  return (
    <SpotlightBackground>
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        whileInView={{ opacity: 1, y: 0 }}
        transition={{
          delay: 0.3,
          duration: 0.8,
          ease: "easeInOut",
        }}
        className="spotlight-inner"
      >
        <div
          className="spotlight-badge"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
            padding: "0.35rem 0.85rem",
            borderRadius: "9999px",
            background: "rgba(99, 102, 241, 0.15)",
            border: "1px solid rgba(99, 102, 241, 0.3)",
            color: "#a5b4fc",
            fontSize: "0.85rem",
            fontWeight: 500,
            marginBottom: "1.25rem",
          }}
        >
          <Sparkles size={14} />
          <span>Next-Gen Skill Matching</span>
        </div>

        <h1 className="spotlight-title">
          Spotlight Background
        </h1>
        <p className="spotlight-description">
          A dramatic and eye-catching animated background effect designed for high-impact project showcases and hero sections.
        </p>

        <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap", justifyContent: "center" }}>
          <button
            className="spotlight-button"
            type="button"
            style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}
          >
            <span>Get Started</span>
            <ArrowRight size={16} />
          </button>
        </div>

        {/* Unsplash Student Collaborator Avatars */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginTop: "2rem" }}>
          <div style={{ display: "flex", marginLeft: "0.5rem" }}>
            <img
              src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=80&h=80&q=80"
              alt="Student Collaborator 1"
              style={{ width: "32px", height: "32px", borderRadius: "9999px", border: "2px solid #0f172a", marginLeft: "-8px", objectFit: "cover" }}
            />
            <img
              src="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=80&h=80&q=80"
              alt="Student Collaborator 2"
              style={{ width: "32px", height: "32px", borderRadius: "9999px", border: "2px solid #0f172a", marginLeft: "-8px", objectFit: "cover" }}
            />
            <img
              src="https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=80&h=80&q=80"
              alt="Student Collaborator 3"
              style={{ width: "32px", height: "32px", borderRadius: "9999px", border: "2px solid #0f172a", marginLeft: "-8px", objectFit: "cover" }}
            />
            <img
              src="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=80&h=80&q=80"
              alt="Student Collaborator 4"
              style={{ width: "32px", height: "32px", borderRadius: "9999px", border: "2px solid #0f172a", marginLeft: "-8px", objectFit: "cover" }}
            />
          </div>
          <span style={{ fontSize: "0.85rem", color: "#94a3b8" }}>
            Joined by <strong>500+</strong> engineering students
          </span>
        </div>
      </motion.div>
    </SpotlightBackground>
  );
};

export default DemoOne;

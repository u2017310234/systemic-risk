"use client";

import { useEffect } from "react";

import { PLAYBACK_WINDOWS } from "@/lib/constants";

type Props = {
  dates: string[];
  selectedDate: string;
  playbackWindow: number;
  isPlaying: boolean;
  onPlaybackWindowChange: (value: number) => void;
  onDateChange: (value: string) => void;
  onPlayingChange: (value: boolean) => void;
};

export function TimelinePlayer(props: Props) {
  const {
    dates,
    selectedDate,
    playbackWindow,
    isPlaying,
    onPlaybackWindowChange,
    onDateChange,
    onPlayingChange
  } = props;

  useEffect(() => {
    if (!isPlaying) {
      return;
    }
    const handle = window.setInterval(() => {
      const currentIndex = dates.indexOf(selectedDate);
      const nextIndex = currentIndex < dates.length - 1 ? currentIndex + 1 : currentIndex;
      onDateChange(dates[nextIndex]);
      if (nextIndex === currentIndex) {
        onPlayingChange(false);
      }
    }, 1500);
    return () => window.clearInterval(handle);
  }, [dates, isPlaying, onDateChange, onPlayingChange, selectedDate]);

  const currentIndex = dates.indexOf(selectedDate);
  const startIndex = Math.max(0, currentIndex - playbackWindow + 1);

  return (
    <div className="rounded-[24px] border border-line/70 bg-panel/80 p-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.24em] text-muted">Timeline</p>
          <p className="mt-2 text-sm text-muted">Replay the latest 30, 90 or 180 available trading days.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {PLAYBACK_WINDOWS.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => onPlaybackWindowChange(value)}
              className={`rounded-full border px-3 py-2 text-sm transition ${
                value === playbackWindow ? "border-accent bg-accent/10 text-text" : "border-line text-muted hover:border-accent/70 hover:text-text"
              }`}
            >
              {value}D
            </button>
          ))}
          <button
            type="button"
            onClick={() => onPlayingChange(!isPlaying)}
            className="rounded-full border border-line px-4 py-2 text-sm transition hover:border-accent/70 hover:text-text"
          >
            {isPlaying ? "Pause" : "Play"}
          </button>
          <button
            type="button"
            onClick={() => onDateChange(dates[Math.min(currentIndex + 1, dates.length - 1)])}
            className="rounded-full border border-line px-4 py-2 text-sm transition hover:border-accent/70 hover:text-text"
          >
            Step
          </button>
        </div>
      </div>

      <div className="mt-5">
        <input
          className="range w-full"
          type="range"
          min={startIndex}
          max={dates.length - 1}
          value={currentIndex}
          onChange={(event) => onDateChange(dates[Number(event.target.value)])}
        />
        <div className="mt-2 flex items-center justify-between text-xs text-muted">
          <span>{dates[startIndex]}</span>
          <span>{selectedDate}</span>
          <span>{dates.at(-1)}</span>
        </div>
      </div>
    </div>
  );
}

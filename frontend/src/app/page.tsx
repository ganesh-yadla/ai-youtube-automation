"use client";

import { useState, type FormEvent } from "react";
import {
  ApiError,
  type AssembledVideo,
  type GenerateVideoResult,
  type Script,
  type TrendAnalysis,
  type TrendSearch,
  type YoutubeUpload,
  generateInsights,
  generateScript,
  generateVideoFromNarration,
  generateVoice,
  mediaUrl,
  publishVideo,
  searchTrends,
} from "@/lib/api";

type Step =
  | "idle"
  | "searching"
  | "analyzing"
  | "ready"
  | "generating_script"
  | "script_review"
  | "generating"
  | "generated"
  | "publishing"
  | "published";

const BUSY_STEPS: Step[] = ["searching", "analyzing", "generating_script", "generating", "publishing"];

// The channel's core content calendar - 5 rotating categories, posted
// daily. Each maps to a search keyword so the existing trend-search flow
// (search real trending videos in this keyword -> analyze -> suggest
// ideas) works unchanged for every category, not just AI tools. Picking
// which category to post is a manual, deliberate choice for now (not
// randomized, not scheduled) - daily rotation/no-repeat tracking across
// categories is still manual; the uniqueness filter already in the
// pipeline catches repeats within a category and across all of them.
const CONTENT_CATEGORIES = [
  { label: "Motivational Speech", keyword: "AI motivational speech shorts" },
  { label: "Animal Facts", keyword: "AI animal facts shorts" },
  { label: "Fitness", keyword: "AI fitness tips shorts" },
  { label: "Facts", keyword: "AI interesting facts shorts" },
  { label: "Stories", keyword: "AI short stories shorts" },
];

export default function Home() {
  const [keyword, setKeyword] = useState("");
  const [search, setSearch] = useState<TrendSearch | null>(null);
  const [analysis, setAnalysis] = useState<TrendAnalysis | null>(null);
  const [selectedIdea, setSelectedIdea] = useState("");
  const [script, setScript] = useState<Script | null>(null);
  const [result, setResult] = useState<GenerateVideoResult | null>(null);
  const [upload, setUpload] = useState<YoutubeUpload | null>(null);
  const [step, setStep] = useState<Step>("idle");
  const [error, setError] = useState<string | null>(null);

  const isBusy = BUSY_STEPS.includes(step);

  async function runSearch(searchKeyword: string) {
    setError(null);
    setSearch(null);
    setAnalysis(null);
    setScript(null);
    setResult(null);
    setUpload(null);
    setSelectedIdea("");

    try {
      setStep("searching");
      const searchResult = await searchTrends(searchKeyword);
      setSearch(searchResult);

      setStep("analyzing");
      const analysisResult = await generateInsights(searchResult.id);
      setAnalysis(analysisResult);
      setStep("ready");
    } catch (err) {
      setError(describeError(err, "Something went wrong searching trends."));
      setStep("idle");
    }
  }

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    const trimmedKeyword = keyword.trim();
    if (!trimmedKeyword) return;
    void runSearch(trimmedKeyword);
  }

  function handleCategorySelect(categoryKeyword: string) {
    setKeyword(categoryKeyword);
    void runSearch(categoryKeyword);
  }

  // Generates the script only, and pauses here for review rather than
  // running straight through to voice/video - a human sees every script
  // before it's narrated, both to catch bad output early and because a
  // pure one-click pipeline with zero human touch is the exact pattern
  // YouTube's 2026 policy flags as "mass-produced, templated" content.
  async function handleGenerateScript() {
    if (!search) return;

    setError(null);
    setScript(null);
    setStep("generating_script");
    try {
      const generated = await generateScript(search.id, selectedIdea.trim() || null);
      setScript(generated);
      setStep("script_review");
    } catch (err) {
      setError(describeError(err, "Something went wrong generating the script."));
      setStep("ready");
    }
  }

  async function handleApproveScript() {
    if (!script) return;

    setError(null);
    setStep("generating");
    try {
      const narration = await generateVoice(script.id);
      const video = await generateVideoFromNarration(narration.id);
      setResult({ script, video });
      setStep("generated");
    } catch (err) {
      setError(describeError(err, "Something went wrong generating the video."));
      setStep("script_review");
    }
  }

  async function handlePublish() {
    if (!result) return;

    setError(null);
    setStep("publishing");
    try {
      const uploaded = await publishVideo(result.video.id);
      setUpload(uploaded);
      setStep("published");
    } catch (err) {
      setError(describeError(err, "Something went wrong publishing to YouTube."));
      setStep("generated");
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-8 px-6 py-12">
      <header>
        <h1 className="text-2xl font-semibold">AI World</h1>
        <p className="text-sm text-neutral-500">Pick today&apos;s category, generate a Short, publish it.</p>
      </header>

      <div className="flex flex-col gap-3">
        <h2 className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
          Today&apos;s category
        </h2>
        <div className="flex flex-wrap gap-2">
          {CONTENT_CATEGORIES.map((category) => (
            <button
              key={category.label}
              type="button"
              onClick={() => handleCategorySelect(category.keyword)}
              disabled={isBusy}
              className={`rounded-md border px-4 py-2 text-sm font-medium transition disabled:opacity-40 ${
                keyword === category.keyword
                  ? "border-neutral-900 bg-neutral-900 text-white"
                  : "border-neutral-900 text-neutral-900 hover:bg-neutral-900 hover:text-white"
              }`}
            >
              {category.label}
            </button>
          ))}
        </div>
        {(step === "searching" || step === "analyzing") && (
          <p className="text-xs text-neutral-400">
            {step === "searching" ? "Searching trends…" : "Analyzing what's working…"}
          </p>
        )}

        <div className="flex items-center gap-3 text-xs text-neutral-400">
          <div className="h-px flex-1 bg-neutral-200" />
          or search your own keyword
          <div className="h-px flex-1 bg-neutral-200" />
        </div>

        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="e.g. AI travel facts shorts"
            disabled={isBusy}
            className="flex-1 rounded-md border border-neutral-300 px-3 py-2 text-sm disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isBusy || !keyword.trim()}
            className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            {step === "searching" ? "Searching…" : step === "analyzing" ? "Analyzing…" : "Find Trends"}
          </button>
        </form>
      </div>

      {error && (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      {analysis && search && (
        <section className="flex flex-col gap-4 border-t border-neutral-200 pt-6">
          <div>
            <h2 className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
              Why these are performing
            </h2>
            <p className="mt-1 text-sm">{analysis.why_performing}</p>
          </div>

          <div>
            <h2 className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
              Pick a video idea
            </h2>
            {analysis.video_ideas.length === 0 && (
              <p className="mt-1 text-sm text-neutral-500">
                All the suggested ideas were too similar to videos you&apos;ve already made. Try
                a different category, search a different keyword, or type your own idea below.
              </p>
            )}
            <div className="mt-2 flex flex-col gap-2">
              {analysis.video_ideas.map((idea) => (
                <button
                  key={idea}
                  type="button"
                  onClick={() => setSelectedIdea(idea)}
                  disabled={isBusy}
                  className={`rounded-md border px-3 py-2 text-left text-sm transition disabled:opacity-50 ${
                    selectedIdea === idea
                      ? "border-neutral-900 bg-neutral-50"
                      : "border-neutral-200 hover:border-neutral-400"
                  }`}
                >
                  {idea}
                </button>
              ))}
            </div>
            <input
              value={selectedIdea}
              onChange={(event) => setSelectedIdea(event.target.value)}
              placeholder="Or type your own idea (optional - leave blank to let AI pick)"
              disabled={isBusy}
              className="mt-2 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm disabled:opacity-50"
            />
          </div>

          <button
            type="button"
            onClick={handleGenerateScript}
            disabled={isBusy}
            className="self-start rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            {step === "generating_script" ? "Writing script…" : "Generate Script"}
          </button>
        </section>
      )}

      {script && !result && (
        <section className="flex flex-col gap-4 border-t border-neutral-200 pt-6">
          <div>
            <h2 className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
              Review the script before it&apos;s narrated
            </h2>
            <p className="mt-1 font-medium">{script.title}</p>
            <p className="mt-1 text-sm text-neutral-600">{script.hook}</p>
          </div>

          <ol className="flex flex-col gap-2">
            {script.segments.map((segment, index) => (
              <li key={index} className="rounded-md border border-neutral-200 px-3 py-2 text-sm">
                <p>{segment.text}</p>
                <p className="mt-1 text-xs text-neutral-400">{segment.visual_description}</p>
              </li>
            ))}
          </ol>

          <p className="text-sm text-neutral-600">{script.cta}</p>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleApproveScript}
              disabled={isBusy}
              className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
            >
              {step === "generating" ? "Generating video… (can take a couple minutes)" : "Approve & Generate Video"}
            </button>
            <button
              type="button"
              onClick={handleGenerateScript}
              disabled={isBusy}
              className="rounded-md border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700 disabled:opacity-40"
            >
              Regenerate Script
            </button>
          </div>
        </section>
      )}

      {result && (
        <section className="flex flex-col gap-4 border-t border-neutral-200 pt-6">
          <ScriptPreview script={result.script} />
          <VideoPreview video={result.video} />

          {upload ? (
            <p className="text-sm">
              Published:{" "}
              <a
                href={upload.youtube_url}
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                {upload.youtube_url}
              </a>{" "}
              — private. Review it and flip it to public yourself in YouTube Studio when ready.
            </p>
          ) : (
            <button
              type="button"
              onClick={handlePublish}
              disabled={isBusy}
              className="self-start rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
            >
              {step === "publishing" ? "Publishing…" : "Publish to YouTube"}
            </button>
          )}
        </section>
      )}
    </main>
  );
}

function ScriptPreview({ script }: { script: Script }) {
  return (
    <div>
      <h2 className="text-xs font-medium tracking-wide text-neutral-500 uppercase">Script</h2>
      <p className="mt-1 font-medium">{script.title}</p>
      <p className="mt-1 text-sm text-neutral-600">{script.hook}</p>
    </div>
  );
}

function VideoPreview({ video }: { video: AssembledVideo }) {
  return (
    <div className="flex flex-wrap items-start gap-4">
      <div>
        <p className="mb-1 text-xs text-neutral-500">Video</p>
        <video
          controls
          src={mediaUrl(video.video_url)}
          poster={mediaUrl(video.thumbnail_url)}
          className="w-48 rounded-md border border-neutral-200"
        />
      </div>
      <div>
        <p className="mb-1 text-xs text-neutral-500">Thumbnail</p>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={mediaUrl(video.thumbnail_url)}
          alt="Generated thumbnail"
          className="w-48 rounded-md border border-neutral-200"
        />
      </div>
    </div>
  );
}

function describeError(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

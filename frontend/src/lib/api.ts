// Typed client for the AI Creator OS backend. Mirrors the FastAPI wire
// schemas in backend/app/api/v1/schemas/ - kept manually in sync since
// there's no shared codegen between the two (a two-service personal
// project doesn't warrant an OpenAPI-client generation step yet).

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(body.detail ?? "Request failed", response.status);
  }

  return response.json() as Promise<T>;
}

export interface TrendingVideo {
  id: string;
  youtube_video_id: string;
  title: string;
  channel_name: string;
  channel_id: string;
  view_count: number;
  published_at: string;
  duration_seconds: number;
  thumbnail_url: string;
  video_url: string;
  estimated_growth_score: number;
  rank_position: number;
}

export interface TrendAnalysis {
  id: string;
  search_id: string;
  why_performing: string;
  common_hooks: string[];
  common_title_patterns: string[];
  common_thumbnail_patterns: string[];
  content_gaps: string[];
  video_ideas: string[];
  ai_model_used: string;
  created_at: string;
}

export interface TrendSearch {
  id: string;
  keyword: string;
  requested_at: string;
  youtube_quota_units_used: number;
  videos: TrendingVideo[];
  analysis: TrendAnalysis | null;
}

export interface ScriptSegment {
  text: string;
  visual_description: string;
}

export interface Script {
  id: string;
  search_id: string;
  video_idea: string;
  title: string;
  hook: string;
  segments: ScriptSegment[];
  cta: string;
  ai_model_used: string;
  created_at: string;
}

export interface AssembledVideo {
  id: string;
  narration_id: string;
  video_url: string;
  thumbnail_url: string;
  duration_seconds: number;
  created_at: string;
}

export interface GenerateVideoResult {
  script: Script;
  video: AssembledVideo;
}

export interface YoutubeUpload {
  id: string;
  video_id: string;
  youtube_video_id: string;
  youtube_url: string;
  uploaded_at: string;
}

export function mediaUrl(relativeUrl: string): string {
  return `${API_URL}${relativeUrl}`;
}

export function searchTrends(keyword: string): Promise<TrendSearch> {
  return request<TrendSearch>("/api/v1/trends/search", {
    method: "POST",
    body: JSON.stringify({ keyword }),
  });
}

export function generateInsights(searchId: string): Promise<TrendAnalysis> {
  return request<TrendAnalysis>(`/api/v1/trends/${searchId}/insights`, { method: "POST" });
}

export function generateVideo(searchId: string, videoIdea: string | null): Promise<GenerateVideoResult> {
  return request<GenerateVideoResult>(`/api/v1/trends/${searchId}/generate-video`, {
    method: "POST",
    body: JSON.stringify({ video_idea: videoIdea }),
  });
}

export function publishVideo(videoId: string): Promise<YoutubeUpload> {
  return request<YoutubeUpload>(`/api/v1/videos/${videoId}/publish`, { method: "POST" });
}

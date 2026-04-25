// Types mirroring backend/app/models/schemas.py — keep in sync.

export const ProficiencyLevel = {
  REMEMBER: 1,
  UNDERSTAND: 2,
  APPLY: 3,
  ANALYZE: 4,
  EVALUATE: 5,
} as const;

export type ProficiencyLevelValue = 1 | 2 | 3 | 4 | 5;

export const ProficiencyLevelName: Record<ProficiencyLevelValue, string> = {
  1: "Remember",
  2: "Understand",
  3: "Apply",
  4: "Analyze",
  5: "Evaluate",
};

export type QuestionType = "conceptual" | "applied" | "debugging" | "design" | "behavioral";

export type ResourceType = "video" | "article" | "course" | "docs" | "project" | "book";

// --- Scorer + GapAnalyzer outputs ---

export interface SkillAssessment {
  skill: string;
  level: ProficiencyLevelValue;
  confidence: number;
  evidence: string[];
  reasoning: string;
  gap_to_required: number | null;
}

export interface SkillGap {
  skill: string;
  required_level: ProficiencyLevelValue;
  current_level: ProficiencyLevelValue | null;
  severity: number;
  adjacent_known_skills: string[];
}

export interface GapAnalysis {
  overall_match_score: number;
  gaps: SkillGap[];
  strengths: string[];
  summary: string;
}

// --- Learning plan ---

export interface LearningResource {
  title: string;
  url: string;
  resource_type: ResourceType;
  source: string;
  estimated_minutes: number;
  reason: string;
}

export interface LearningModule {
  skill: string;
  target_level: ProficiencyLevelValue;
  estimated_hours_min: number;
  estimated_hours_max: number;
  prerequisites: string[];
  resources: LearningResource[];
  rationale: string;
}

export interface LearningPlan {
  candidate_name: string | null;
  target_role: string;
  total_hours_min: number;
  total_hours_max: number;
  modules: LearningModule[];
  suggested_order: string[];
  summary: string;
}

// --- API shapes ---

export interface QuestionPayload {
  skill: string;
  skill_index: number;
  skills_total: number;
  question: string;
  bloom_level: ProficiencyLevelValue;
  theta_before: number;
}

export interface StartAssessmentResponse {
  session_id: string;
  status: "awaiting_response" | "complete" | "error";
  next_question: QuestionPayload | null;
  message?: string | null;
}

export interface RespondResponse {
  session_id: string;
  status: "awaiting_response" | "complete";
  next_question: QuestionPayload | null;
  interview_complete: boolean;
}

export interface AssessmentResultResponse {
  session_id: string;
  skill_assessments: SkillAssessment[];
  gap_analysis: GapAnalysis | null;
  learning_plan: LearningPlan | null;
  irt_thetas: Record<string, number>;
}

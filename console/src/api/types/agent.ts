export interface AgentRequest {
  input: unknown;
  session_id?: string | null;
  user_id?: string | null;
  channel?: string | null;
  [key: string]: unknown;
}

export interface ContextCompactConfig {
  enabled: boolean;
  compact_threshold_ratio: number;
  reserve_threshold_ratio: number;
  compact_with_thinking_block: boolean;
}

export interface ToolResultPruningConfig {
  enabled: boolean;
  pruning_recent_n: number;
  pruning_old_msg_max_bytes: number;
  pruning_recent_msg_max_bytes: number;
  offload_retention_days: number;
  exempt_file_extensions: string[];
  exempt_tool_names: string[];
}

export interface LightContextConfig {
  dialog_path: string;
  token_count_estimate_divisor: number;
  context_compact_config: ContextCompactConfig;
  tool_result_pruning_config: ToolResultPruningConfig;
}

export interface AutoMemorySearchConfig {
  enabled: boolean;
  max_results: number;
  min_score: number;
}

export interface EmbeddingModelConfig {
  backend: string;
  api_key: string;
  base_url: string;
  model_name: string;
  dimensions: number;
  enable_cache: boolean;
  use_dimensions: boolean;
  max_cache_size: number;
  max_input_length: number;
  max_batch_size: number;
}

export interface ReMeLightMemoryConfig {
  summarize_when_compact: boolean;
  auto_memory_interval: number | null;
  dream_cron: string;
  auto_memory_search_config: AutoMemorySearchConfig;
  embedding_model_config: EmbeddingModelConfig;
  rebuild_memory_index_on_start: boolean;
  recursive_file_watcher: boolean;
}

export interface MemosMemoryConfig {
  memos_url: string;
  api_key: string;
  user_id: string;
  cube_name: string;
  create_cube_if_not_exists: boolean;
  top_k: number;
  search_mode: string;
  relativity_threshold: number;
  fallback_to_reme_light: boolean;
  timeout_seconds: number;
  summarize_when_compact: boolean;
  auto_memory_interval: number | null;
  memory_tool_visible: boolean;
  // 运行时状态字段
  memos_status?: string;
  memos_error_msg?: string;
  memos_last_check?: string;
}

export interface AutoTitleConfig {
  enabled: boolean;
  timeout_seconds: number;
}

export interface AgentsRunningConfig {
  max_iters: number;
  auto_continue_on_text_only: boolean;
  shell_command_timeout: number;
  llm_retry_enabled: boolean;
  llm_max_retries: number;
  llm_backoff_base: number;
  llm_backoff_cap: number;
  llm_max_concurrent: number;
  llm_max_qpm: number;
  llm_rate_limit_pause: number;
  llm_rate_limit_jitter: number;
  llm_acquire_timeout: number;
  max_input_length: number;
  history_max_length: number;
  context_manager_backend: string;
  light_context_config: LightContextConfig;
  memory_manager_backend: string;
  reme_light_memory_config: ReMeLightMemoryConfig;
  memos_memory_config: MemosMemoryConfig;
  approval_level?: string;
  auto_title_config: AutoTitleConfig;
}

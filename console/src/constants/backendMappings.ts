import type { ComponentType } from "react";
import { LightContextCard } from "../pages/Agent/Config/components/LightContextCard";
import { ReMeLightMemoryCard } from "../pages/Agent/Config/components/ReMeLightMemoryCard";
import { MemosMemoryCard } from "../pages/Agent/Config/components/MemosMemoryCard";

interface BackendMapping<T> {
  configField: string;
  component: ComponentType<T>;
  label: string;
  tabKey: string;
}

export const CONTEXT_MANAGER_BACKEND_MAPPINGS: Record<
  string,
  BackendMapping<{ maxInputLength: number }>
> = {
  light: {
    configField: "light_context_config",
    component: LightContextCard,
    label: "light",
    tabKey: "lightContext",
  },
};

export const MEMORY_MANAGER_BACKEND_MAPPINGS: Record<
  string,
  BackendMapping<object>
> = {
  remelight: {
    configField: "reme_light_memory_config",
    component: ReMeLightMemoryCard,
    label: "remelight",
    tabKey: "remeLightMemory",
  },
  memos: {
    configField: "memos_memory_config",
    component: MemosMemoryCard,
    label: "memos",
    tabKey: "memosMemory",
  },
};

export const CONTEXT_MANAGER_BACKEND_OPTIONS = Object.entries(
  CONTEXT_MANAGER_BACKEND_MAPPINGS,
).map(([value, { label }]) => ({ value, label }));

export const MEMORY_MANAGER_BACKEND_OPTIONS = Object.entries(
  MEMORY_MANAGER_BACKEND_MAPPINGS,
).map(([value, { label }]) => ({ value, label }));

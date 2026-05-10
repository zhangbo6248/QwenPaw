import {
  Form,
  Card,
  Switch,
  InputNumber,
  Input,
  Collapse,
  Select,
  Slider,
} from "@agentscope-ai/design";
import { useTranslation } from "react-i18next";
import styles from "../index.module.less";

export function MemosMemoryCard() {
  const { t } = useTranslation();

  return (
    <Card
      className={styles.formCard}
      title={t("agentConfig.memosMemoryTitle")}
    >
      {/* 兼容性配置 - 顶层 */}
      <Form.Item
        label={t("agentConfig.fallbackToReMeLight")}
        name={["memos_memory_config", "fallback_to_reme_light"]}
        valuePropName="checked"
        tooltip={t("agentConfig.fallbackToReMeLightTooltip")}
      >
        <Switch />
      </Form.Item>

      {/* 连接配置 - 顶层 */}
      <Form.Item
        label={t("agentConfig.memosUrl")}
        name={["memos_memory_config", "memos_url"]}
        tooltip={t("agentConfig.memosUrlTooltip")}
        initialValue="http://memos-api:8000"
      >
        <Input placeholder="http://memos-api:8000" />
      </Form.Item>

      <Form.Item
        label={t("agentConfig.memosApiKey")}
        name={["memos_memory_config", "api_key"]}
        tooltip={t("agentConfig.memosApiKeyTooltip")}
      >
        <Input.Password placeholder={t("agentConfig.memosApiKeyPlaceholder")} />
      </Form.Item>

      <Form.Item
        label={t("agentConfig.memosUserId")}
        name={["memos_memory_config", "user_id"]}
        tooltip={t("agentConfig.memosUserIdTooltip")}
        initialValue="qwenpaw"
      >
        <Input placeholder="qwenpaw" />
      </Form.Item>

      {/* Search Configuration 折叠区 */}
      <Collapse
        items={[
          {
            key: "searchConfig",
            label: t("agentConfig.searchConfigCollapseLabel"),
            children: (
              <>
                <Form.Item
                  label={t("agentConfig.topK")}
                  name={["memos_memory_config", "top_k"]}
                  tooltip={t("agentConfig.topKTooltip")}
                  initialValue={5}
                >
                  <InputNumber
                    style={{ width: "100%" }}
                    min={1}
                    max={50}
                    step={1}
                  />
                </Form.Item>

                <Form.Item
                  label={t("agentConfig.searchMode")}
                  name={["memos_memory_config", "search_mode"]}
                  tooltip={t("agentConfig.searchModeTooltip")}
                  initialValue="fast"
                >
                  <Select
                    options={[
                      { value: "fast", label: t("agentConfig.searchModeFast") },
                      { value: "fine", label: t("agentConfig.searchModeFine") },
                      { value: "mixture", label: t("agentConfig.searchModeMixture") },
                    ]}
                  />
                </Form.Item>

                <Form.Item
                  label={t("agentConfig.relativityThreshold")}
                  name={["memos_memory_config", "relativity_threshold"]}
                  tooltip={t("agentConfig.relativityThresholdTooltip")}
                  initialValue={0.45}
                >
                  <Slider
                    min={0}
                    max={1}
                    step={0.05}
                    marks={{
                      0: "0",
                      0.45: "0.45",
                      0.5: "0.5",
                      1: "1",
                    }}
                  />
                </Form.Item>
              </>
            ),
          },
        ]}
      />

      {/* Advanced 折叠区 */}
      <Collapse
        items={[
          {
            key: "advanced",
            label: t("agentConfig.advancedCollapseLabel"),
            children: (
              <>
                <Form.Item
                  label={t("agentConfig.cubeName")}
                  name={["memos_memory_config", "cube_name"]}
                  tooltip={t("agentConfig.cubeNameTooltip")}
                  initialValue="qwenpaw"
                >
                  <Input placeholder="qwenpaw" />
                </Form.Item>

                <Form.Item
                  label={t("agentConfig.createCubeIfNotExists")}
                  name={["memos_memory_config", "create_cube_if_not_exists"]}
                  valuePropName="checked"
                  tooltip={t("agentConfig.createCubeIfNotExistsTooltip")}
                  initialValue={true}
                >
                  <Switch />
                </Form.Item>

                <Form.Item
                  label={t("agentConfig.timeoutSeconds")}
                  name={["memos_memory_config", "timeout_seconds"]}
                  tooltip={t("agentConfig.timeoutSecondsTooltip")}
                  initialValue={30}
                >
                  <InputNumber
                    style={{ width: "100%" }}
                    min={5}
                    max={120}
                    step={5}
                  />
                </Form.Item>

                {/* 自动存储配置 */}
                <Form.Item
                  label={t("agentConfig.summarizeWhenCompact")}
                  name={["memos_memory_config", "summarize_when_compact"]}
                  valuePropName="checked"
                  tooltip={t("agentConfig.summarizeWhenCompactTooltip")}
                  initialValue={true}
                >
                  <Switch />
                </Form.Item>

                <Form.Item
                  label={t("agentConfig.autoMemoryInterval")}
                  name={["memos_memory_config", "auto_memory_interval"]}
                  tooltip={t("agentConfig.autoMemoryIntervalTooltip")}
                >
                  <InputNumber
                    style={{ width: "100%" }}
                    min={1}
                    max={20}
                    placeholder={t("agentConfig.autoMemoryIntervalPlaceholder")}
                  />
                </Form.Item>
              </>
            ),
          },
        ]}
      />
    </Card>
  );
}
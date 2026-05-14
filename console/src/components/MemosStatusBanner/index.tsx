import { Alert, Button, Space } from "antd";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

interface MemosStatusBannerProps {
  status: string;
  errorMsg?: string | null;
  onSwitchToReMeLight?: () => void;
}

export const MemosStatusBanner: React.FC<MemosStatusBannerProps> = ({
  status,
  errorMsg,
  onSwitchToReMeLight,
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  if (status === "healthy" || status === "unknown") {
    return null;
  }

  const isDegraded = status === "degraded";
  const isError = status === "error";

  const title = isDegraded
    ? t("agentConfig.memosDegradedTitle", "⚠️ MemOS 当前不可用")
    : t("agentConfig.memosErrorTitle", "🚫 MemOS 连接失败");

  const description = errorMsg || (isDegraded
    ? t("agentConfig.memosDegradedDesc", "记忆功能暂时不可��，请检查配置或切换到 ReMeLight")
    : t("agentConfig.memosErrorDesc", "请进入配置页面切换到 ReMeLight 以继续使用"));

  return (
    <Alert
      message={title}
      description={
        <Space direction="vertical" size="small">
          <span>{description}</span>
          <Space>
            <Button
              size="small"
              type="primary"
              onClick={() => navigate("/agent/config")}
            >
              {t("agentConfig.goToConfig", "查看配置")}
            </Button>
            {onSwitchToReMeLight && (
              <Button
                size="small"
                onClick={onSwitchToReMeLight}
              >
                {t("agentConfig.switchToReMeLight", "切换到 ReMeLight")}
              </Button>
            )}
          </Space>
        </Space>
      }
      type={isError ? "error" : "warning"}
      showIcon
      closable
      style={{ margin: "8px 16px", borderRadius: 0 }}
    />
  );
};

export default MemosStatusBanner;
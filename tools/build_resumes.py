"""Build the one-page data-analysis and data-engineering resumes."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf"
OUTPUT.mkdir(parents=True, exist_ok=True)

REGULAR_FONT = Path(r"C:\Windows\Fonts\Deng.ttf")
BOLD_FONT = Path(r"C:\Windows\Fonts\Dengb.ttf")
pdfmetrics.registerFont(TTFont("ResumeCN", str(REGULAR_FONT)))
pdfmetrics.registerFont(TTFont("ResumeCN-Bold", str(BOLD_FONT)))
pdfmetrics.registerFontFamily(
    "ResumeCN",
    normal="ResumeCN",
    bold="ResumeCN-Bold",
    italic="ResumeCN",
    boldItalic="ResumeCN-Bold",
)

INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#4B5563")
ACCENT = colors.HexColor("#1D4ED8")
LINE = colors.HexColor("#9CA3AF")
PAPER = colors.white


def _styles():
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle(
            "name",
            parent=base["Normal"],
            fontName="ResumeCN-Bold",
            fontSize=27,
            leading=31,
            alignment=TA_CENTER,
            textColor=INK,
            spaceAfter=1.8 * mm,
        ),
        "contact": ParagraphStyle(
            "contact",
            parent=base["Normal"],
            fontName="ResumeCN",
            fontSize=9.4,
            leading=12.5,
            alignment=TA_CENTER,
            textColor=MUTED,
            spaceAfter=2.8 * mm,
        ),
        "section": ParagraphStyle(
            "section",
            parent=base["Normal"],
            fontName="ResumeCN-Bold",
            fontSize=13.2,
            leading=16,
            textColor=INK,
            spaceBefore=1.8 * mm,
            spaceAfter=0.8 * mm,
        ),
        "entry": ParagraphStyle(
            "entry",
            parent=base["Normal"],
            fontName="ResumeCN-Bold",
            fontSize=10.4,
            leading=13,
            textColor=INK,
        ),
        "date": ParagraphStyle(
            "date",
            parent=base["Normal"],
            fontName="ResumeCN-Bold",
            fontSize=9.8,
            leading=13,
            alignment=TA_RIGHT,
            textColor=INK,
        ),
        "role": ParagraphStyle(
            "role",
            parent=base["Normal"],
            fontName="ResumeCN",
            fontSize=9.2,
            leading=11.8,
            textColor=MUTED,
        ),
        "role_right": ParagraphStyle(
            "role_right",
            parent=base["Normal"],
            fontName="ResumeCN",
            fontSize=9.2,
            leading=11.8,
            alignment=TA_RIGHT,
            textColor=MUTED,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontName="ResumeCN",
            fontSize=9.25,
            leading=13.55,
            leftIndent=4.1 * mm,
            firstLineIndent=-3.1 * mm,
            bulletIndent=0.6 * mm,
            textColor=INK,
            wordWrap="CJK",
            spaceAfter=0.72 * mm,
        ),
        "skill": ParagraphStyle(
            "skill",
            parent=base["Normal"],
            fontName="ResumeCN",
            fontSize=9.0,
            leading=13.0,
            leftIndent=4.1 * mm,
            firstLineIndent=-3.1 * mm,
            bulletIndent=0.6 * mm,
            textColor=INK,
            wordWrap="CJK",
            spaceAfter=0.6 * mm,
        ),
    }


def _section(title, styles):
    return [
        Paragraph(title, styles["section"]),
        HRFlowable(width="100%", thickness=0.55, color=LINE, spaceAfter=1.1 * mm),
    ]


def _entry_header(title, date, role, location, styles, link=None):
    if link:
        title_html = (
            f'{title}<br/><font name="ResumeCN" size="8.6">个人项目｜'
            f'<link href="{link}" color="#1D4ED8">{link}</link></font>'
        )
    else:
        title_html = title
    rows = [
        [Paragraph(title_html, styles["entry"]), Paragraph(date, styles["date"])],
    ]
    if role or location:
        rows.append(
            [Paragraph(role or "", styles["role"]), Paragraph(location or "", styles["role_right"])]
        )
    table = Table(rows, colWidths=[135 * mm, 45 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.25 * mm),
            ]
        )
    )
    return table


def _bullet(text, styles, skill=False):
    return Paragraph(f"•&nbsp;&nbsp;{text}", styles["skill" if skill else "bullet"])


def _experience(title, date, role, location, bullets, styles, link=None):
    content = [_entry_header(title, date, role, location, styles, link)]
    content.extend(_bullet(text, styles) for text in bullets)
    content.append(Spacer(1, 1.2 * mm))
    return KeepTogether(content)


def _education(styles):
    return KeepTogether(
        [
            _entry_header(
                "上海财经大学｜计算机科学与技术｜本科",
                "2023–2027",
                "",
                "",
                styles,
            ),
            _bullet(
                "<b>主修课程：</b>数据库原理、数据结构、大数据处理技术、Python程序设计、数理统计、机器学习",
                styles,
            ),
        ]
    )


COMMON_INTERNSHIP = [
    (
        "益普索（中国）咨询有限公司上海分公司",
        "2026年1月–2026年9月",
        "数据工程实习生",
        "上海",
    ),
    (
        "上海三高计算机中心股份有限公司",
        "2025年7月–2025年9月",
        "数据分析实习生",
        "上海",
    ),
]


ANALYSIS_CONTENT = {
    "ipsos": [
        "面向小红书、京东、天猫、Ozon及微信指数搭建多平台数据采集与清洗流程，日均处理<b>2万+</b>条数据，关键字段完整率达到<b>98%+</b>、抽样准确率达到<b>95%+</b>。",
        "统一不同平台的字段映射和数据口径，对半结构化数据完成去重、异常处理与标准化，为品牌监测、竞品追踪及社媒舆情分析提供稳定数据源。",
        "将清洗数据建模导入ClickHouse，支持咨询团队按品牌、平台、时间等维度开展实时查询和对比分析，核心查询响应时间低于<b>200ms</b>。",
    ],
    "sangao": [
        "参与“北京原水调度项目”，使用SQL与Python（Pandas）对<b>100万+</b>条管网及时空数据完成多表关联、缺失处理、异常检测和字段标准化，为后续分析建立可靠数据基础。",
        "使用三高宏扬供水管网水力模拟软件开展管网水力模拟、工况对比及结果可视化，辅助评估不同调度方案下的管网运行状态。",
    ],
    "project": [
        "对Ozon、Wildberries、Yandex Market俄语评论与问答进行可复现数据审计，对账<b>97,265</b>行原始记录与<b>86,378</b>行合并数据，定位链路缺失、正文缺失、评分偏斜及翻译中断等质量问题。",
        "围绕产品口碑建立评分分布、月度趋势、平台对比、地域分布及日历热力等<b>20+</b>项指标，使用窗口函数、CASE及日期函数完成多维SQL聚合。",
        "调用DeepSeek完成情感、意图、实体及差评根因分析，通过内容哈希缓存、增量处理与断点续传减少重复调用，并保留规则分析作为降级方案。",
        "使用ECharts 5.5开发<b>7页</b>交互式分析看板，支持产品、平台和时间动态筛选，集中呈现口碑趋势、问答需求与差评诊断。",
    ],
    "skills": [
        "<b>数据分析：</b>SQL复杂查询、窗口函数、多表关联；Python（Pandas/NumPy）数据处理、描述性统计及数据质量诊断。",
        "<b>报表与可视化：</b>Excel数据透视表、Power Query、VLOOKUP；ECharts交互式看板开发及指标设计。",
        "<b>数据工程：</b>ETL、增量处理、质量校验、星型模型；具备Airflow DAG与GitHub Actions工作流开发经验。",
        "<b>数据库与工具：</b>MySQL、ClickHouse、Git、Linux、Selenium、Scrapy；CET-6，能够阅读英文技术文档。",
    ],
}


ENGINEERING_CONTENT = {
    "ipsos": [
        "独立设计覆盖小红书、京东、天猫、Ozon及微信指数的数据接入方案，按平台特征使用自动化插件、Selenium和网络请求分析，统一字段映射与输出格式。",
        "针对动态加载、访问频控及接口参数变化设计代理轮换、请求适配和质量校验，日均处理<b>2万+</b>条有效数据，关键字段完整率达到<b>98%+</b>、抽样准确率达到<b>95%+</b>。",
        "完成半结构化数据清洗、去重和标准化并建模导入ClickHouse，支撑品牌监测、竞品追踪和舆情分析，核心查询响应时间低于<b>200ms</b>。",
    ],
    "sangao": [
        "参与“北京原水调度项目”，使用SQL与Python（Pandas）对<b>100万+</b>条管网及时空数据完成多表关联、清洗、异常检测和字段标准化，为水力模型提供标准数据集。",
        "使用三高宏扬供水管网水力模拟软件开展水力模拟和结果可视化，辅助比较不同调度工况，为原水调度策略评估提供数据依据。",
    ],
    "project": [
        "使用Python/Pandas构建Ozon、Wildberries、Yandex Market多源ETL，完成文件解析、字段映射、日期标准化、异常处理、内容去重及增量写入MySQL。",
        "采用星型模型设计反馈事实表及产品、平台、日期维表，建立ETL运行统计与质量剖析，自动检查字段缺失、重复记录、未来日期和评分越界。",
        "编写一键管道及Airflow DAG定义，串联ETL、翻译、分析、指标生成和质量检查；配置失败重试、执行超时，并通过GitHub Actions和Webhook支持月度采集与自动部署。",
        "在<b>2核2GB</b>阿里云ECS搭建Hadoop 3.2.4与Spark 3.5.9伪分布式环境，创建ODS/DWD/DWS/ADS目录并完成Spark读写HDFS Parquet验证。",
    ],
    "skills": [
        "<b>编程与查询：</b>Python（Pandas/NumPy/正则表达式）；SQL复杂查询、窗口函数、索引设计及查询优化。",
        "<b>数仓与数据工程：</b>ETL/ELT、全量与增量同步、数据质量校验、星型模型；掌握HDFS/Spark部署及基础作业实践。",
        "<b>存储与部署：</b>MySQL、ClickHouse；阿里云ECS、Linux、Nginx、GitHub Actions和Webhook部署。",
        "<b>工程工具：</b>Git、Selenium、Scrapy；具备任务日志排查、异常重试和流程监控意识；CET-6。",
    ],
}


def build_resume(output_name, project_title, content):
    styles = _styles()
    output_path = OUTPUT / output_name
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=10.5 * mm,
        bottomMargin=9.5 * mm,
        title=output_name.removesuffix(".pdf"),
        author="卢子旭",
        subject=project_title,
    )

    story = [
        Paragraph("卢子旭", styles["name"]),
        Paragraph(
            '<link href="mailto:2608943895@qq.com" color="#1D4ED8">2608943895@qq.com</link>'
            "　·　(+86) 13225251072",
            styles["contact"],
        ),
    ]
    story.extend(_section("教育背景", styles))
    story.append(_education(styles))
    story.extend(_section("实习经历", styles))
    story.append(
        _experience(*COMMON_INTERNSHIP[0], content["ipsos"], styles)
    )
    story.append(
        _experience(*COMMON_INTERNSHIP[1], content["sangao"], styles)
    )
    story.extend(_section("项目经历", styles))
    story.append(
        _experience(
            project_title,
            "2026年2月–至今",
            "",
            "",
            content["project"],
            styles,
            "https://github.com/lzx141/Russia-vivo-review-qa",
        )
    )
    story.extend(_section("个人技能", styles))
    story.extend(_bullet(item, styles, skill=True) for item in content["skills"])

    document.build(story)
    return output_path


if __name__ == "__main__":
    outputs = [
        build_resume(
            "卢子旭_数据分析师_2026秋招.pdf",
            "俄罗斯跨境电商多源用户反馈分析",
            ANALYSIS_CONTENT,
        ),
        build_resume(
            "卢子旭_数据工程师_2026秋招.pdf",
            "跨境电商多源用户反馈数据平台",
            ENGINEERING_CONTENT,
        ),
    ]
    for path in outputs:
        print(path)

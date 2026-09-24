/**
 * 古籍版本目录数据库 · 核心典籍版本信息
 * 格式: { title, author, dynasty, category, versions[], notes }
 */
const VERSIONS_DB = [
  // ═══════════════════════════════════════════════════════════════
  // 先秦典籍
  // ═══════════════════════════════════════════════════════════════
  {
    title: "尚书",
    author: "佚名（相传孔子编订）",
    dynasty: "先秦",
    category: "经部",
    versions: [
      { type: "古写本", name: "敦煌写本", era: "唐", notes: "敦煌遗书" },
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "存残卷" },
      { type: "现代整理", name: "中华书局《十三经注疏》本", era: "现代", notes: "1980年影印" },
      { type: "现代整理", name: "上海古籍出版社《尚书正义》", era: "现代", notes: "2007年" },
    ],
    notes: "儒家五经之一，今文28篇，古文25篇"
  },
  {
    title: "诗经",
    author: "佚名（相传孔子删订）",
    dynasty: "先秦",
    category: "经部",
    versions: [
      { type: "古写本", name: "唐写本毛诗正义", era: "唐", notes: "敦煌遗书" },
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "" },
      { type: "明刻本", name: "明毛氏汲古阁本", era: "明", notes: "毛晋刻" },
      { type: "现代整理", name: "中华书局《十三经注疏》本", era: "现代", notes: "1980年影印" },
      { type: "现代整理", name: "上海古籍出版社《诗集传》", era: "现代", notes: "朱熹注" },
    ],
    notes: "儒家五经之一，305篇，风、雅、颂"
  },
  {
    title: "周礼",
    author: "佚名",
    dynasty: "先秦",
    category: "经部",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "" },
      { type: "现代整理", name: "中华书局《十三经注疏》本", era: "现代", notes: "" },
    ],
    notes: "儒家三礼之一，六官制度"
  },
  {
    title: "仪礼",
    author: "佚名",
    dynasty: "先秦",
    category: "经部",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "" },
      { type: "现代整理", name: "中华书局《十三经注疏》本", era: "现代", notes: "" },
    ],
    notes: "儒家三礼之一，古代礼仪规范"
  },
  {
    title: "礼记",
    author: "戴圣编",
    dynasty: "西汉",
    category: "经部",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "" },
      { type: "现代整理", name: "中华书局《十三经注疏》本", era: "现代", notes: "" },
      { type: "现代整理", name: "中华书局《礼记正义》", era: "现代", notes: "郑玄注、孔颖达疏" },
    ],
    notes: "儒家三礼之一，49篇"
  },
  {
    title: "春秋左氏传",
    author: "左丘明",
    dynasty: "先秦",
    category: "经部",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "" },
      { type: "现代整理", name: "中华书局《十三经注疏》本", era: "现代", notes: "" },
      { type: "现代整理", name: "上海古籍出版社《春秋左传注》", era: "现代", notes: "杨伯峻注，1981年" },
    ],
    notes: "《春秋》三传之一，编年体史书"
  },
  {
    title: "春秋公羊传",
    author: "公羊高",
    dynasty: "西汉",
    category: "经部",
    versions: [
      { type: "现代整理", name: "中华书局《十三经注疏》本", era: "现代", notes: "" },
    ],
    notes: "《春秋》三传之一，今文经学"
  },
  {
    title: "春秋穀梁传",
    author: "穀梁赤",
    dynasty: "西汉",
    category: "经部",
    versions: [
      { type: "现代整理", name: "中华书局《十三经注疏》本", era: "现代", notes: "" },
    ],
    notes: "《春秋》三传之一"
  },
  {
    title: "论语",
    author: "孔子弟子及再传弟子",
    dynasty: "先秦",
    category: "经部",
    versions: [
      { type: "古写本", name: "唐写本", era: "唐", notes: "敦煌遗书" },
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "" },
      { type: "现代整理", name: "中华书局《论语译注》", era: "现代", notes: "杨伯峻译注，1980年" },
      { type: "现代整理", name: "商务印书馆《论语今读》", era: "现代", notes: "李泽厚" },
    ],
    notes: "儒家四书之一，20篇"
  },
  {
    title: "孟子",
    author: "孟轲",
    dynasty: "战国",
    category: "经部",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "" },
      { type: "现代整理", name: "中华书局《孟子译注》", era: "现代", notes: "杨伯峻译注" },
    ],
    notes: "儒家四书之一，7篇"
  },
  {
    title: "孝经",
    author: "佚名",
    dynasty: "先秦",
    category: "经部",
    versions: [
      { type: "现代整理", name: "中华书局《十三经注疏》本", era: "现代", notes: "" },
    ],
    notes: "儒家经典，18章"
  },
  {
    title: "尔雅",
    author: "佚名",
    dynasty: "先秦",
    category: "经部",
    versions: [
      { type: "现代整理", name: "中华书局《十三经注疏》本", era: "现代", notes: "" },
    ],
    notes: "中国最早词典，19篇"
  },
  {
    title: "周易",
    author: "伏羲/文王/孔子（传说）",
    dynasty: "先秦",
    category: "经部",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "" },
      { type: "现代整理", name: "中华书局《周易正义》", era: "现代", notes: "王弼注、孔颖达疏" },
      { type: "现代整理", name: "中华书局《周易译注》", era: "现代", notes: "黄寿祺、张善文" },
    ],
    notes: "儒家五经之首，经传合一"
  },
  {
    title: "老子",
    author: "李耳",
    dynasty: "先秦",
    category: "子部",
    versions: [
      { type: "古写本", name: "郭店楚简老子", era: "战国", notes: "1993年出土，最早版本" },
      { type: "古写本", name: "马王堆帛书老子", era: "西汉", notes: "1973年出土，甲乙本" },
      { type: "现代整理", name: "中华书局《老子道德经注》", era: "现代", notes: "王弼注" },
      { type: "现代整理", name: "中华书局《老子今注今译》", era: "现代", notes: "陈鼓应" },
    ],
    notes: "道家经典，81章，约5000字"
  },
  {
    title: "庄子",
    author: "庄周",
    dynasty: "战国",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《庄子集释》", era: "现代", notes: "郭庆藩集释" },
      { type: "现代整理", name: "中华书局《庄子今注今译》", era: "现代", notes: "陈鼓应" },
    ],
    notes: "道家经典，33篇（内7外15杂11）"
  },
  {
    title: "墨子",
    author: "墨翟",
    dynasty: "战国",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《墨子间诂》", era: "现代", notes: "孙诒让" },
    ],
    notes: "墨家经典，53篇"
  },
  {
    title: "荀子",
    author: "荀况",
    dynasty: "战国",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《荀子集解》", era: "现代", notes: "王先谦" },
    ],
    notes: "儒家经典，32篇"
  },
  {
    title: "韩非子",
    author: "韩非",
    dynasty: "战国",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《韩非子集解》", era: "现代", notes: "王先慎" },
    ],
    notes: "法家经典，55篇"
  },
  {
    title: "孙子兵法",
    author: "孙武",
    dynasty: "春秋",
    category: "子部",
    versions: [
      { type: "古写本", name: "银雀山汉简", era: "西汉", notes: "1972年出土" },
      { type: "现代整理", name: "中华书局《十一家注孙子》", era: "现代", notes: "" },
      { type: "现代整理", name: "文物出版社《孙子兵法》", era: "现代", notes: "" },
    ],
    notes: "兵家经典，13篇"
  },
  {
    title: "吕氏春秋",
    author: "吕不韦集门客编",
    dynasty: "战国",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《吕氏春秋集释》", era: "现代", notes: "许维遹" },
    ],
    notes: "杂家，160篇，十二纪八览六论"
  },
  {
    title: "战国策",
    author: "刘向编订",
    dynasty: "西汉",
    category: "史部",
    versions: [
      { type: "现代整理", name: "中华书局《战国策》", era: "现代", notes: "1978年" },
      { type: "现代整理", name: "上海古籍出版社《战国策》", era: "现代", notes: "" },
    ],
    notes: "国别体史书，33卷"
  },
  {
    title: "山海经",
    author: "佚名",
    dynasty: "先秦",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《山海经校注》", era: "现代", notes: "袁珂校注" },
    ],
    notes: "地理神话著作，18卷"
  },
  {
    title: "楚辞",
    author: "屈原等",
    dynasty: "战国",
    category: "集部",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "" },
      { type: "现代整理", name: "中华书局《楚辞补注》", era: "现代", notes: "洪兴祖" },
      { type: "现代整理", name: "中华书局《楚辞集注》", era: "现代", notes: "朱熹" },
    ],
    notes: "浪漫主义诗歌总集"
  },

  // ═══════════════════════════════════════════════════════════════
  // 两汉典籍
  // ═══════════════════════════════════════════════════════════════
  {
    title: "春秋繁露",
    author: "董仲舒",
    dynasty: "西汉",
    category: "经部",
    versions: [
      { type: "现代整理", name: "中华书局《春秋繁露义证》", era: "现代", notes: "苏舆" },
    ],
    notes: "今文经学，17卷"
  },
  {
    title: "盐铁论",
    author: "桓宽",
    dynasty: "西汉",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《盐铁论校注》", era: "现代", notes: "王利器" },
    ],
    notes: "记录盐铁会议，60篇"
  },
  {
    title: "新序",
    author: "刘向",
    dynasty: "西汉",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《新序校释》", era: "现代", notes: "" },
    ],
    notes: "10卷"
  },
  {
    title: "说苑",
    author: "刘向",
    dynasty: "西汉",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《说苑校证》", era: "现代", notes: "" },
    ],
    notes: "20卷"
  },
  {
    title: "列女传",
    author: "刘向",
    dynasty: "西汉",
    category: "史部",
    versions: [
      { type: "现代整理", name: "中华书局《列女传注》", era: "现代", notes: "" },
    ],
    notes: "7卷，中国最早妇女传记"
  },
  {
    title: "法言",
    author: "扬雄",
    dynasty: "西汉",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《法言义疏》", era: "现代", notes: "" },
    ],
    notes: "13篇，仿《论语》"
  },
  {
    title: "太玄",
    author: "扬雄",
    dynasty: "西汉",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《太玄校释》", era: "现代", notes: "" },
    ],
    notes: "仿《周易》"
  },
  {
    title: "方言",
    author: "扬雄",
    dynasty: "西汉",
    category: "小学",
    versions: [
      { type: "现代整理", name: "中华书局《方言笺疏》", era: "现代", notes: "" },
    ],
    notes: "中国最早方言学著作"
  },
  {
    title: "说文解字",
    author: "许慎",
    dynasty: "东汉",
    category: "小学",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "北宋", notes: "存最早刻本" },
      { type: "现代整理", name: "中华书局《说文解字》", era: "现代", notes: "1963年影印陈昌治刻本" },
      { type: "现代整理", name: "中华书局《说文解字注》", era: "现代", notes: "段玉裁注" },
    ],
    notes: "中国最早字典，9353字，540部首"
  },
  {
    title: "释名",
    author: "刘熙",
    dynasty: "东汉",
    category: "小学",
    versions: [
      { type: "现代整理", name: "中华书局《释名疏证补》", era: "现代", notes: "王先谦" },
    ],
    notes: "声训词典，27篇"
  },
  {
    title: "白虎通义",
    author: "班固等",
    dynasty: "东汉",
    category: "经部",
    versions: [
      { type: "现代整理", name: "中华书局《白虎通疏证》", era: "现代", notes: "陈立" },
    ],
    notes: "记录白虎观会议，今文经学"
  },
  {
    title: "论衡",
    author: "王充",
    dynasty: "东汉",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《论衡校释》", era: "现代", notes: "黄晖" },
      { type: "现代整理", name: "上海人民出版社《论衡》", era: "现代", notes: "" },
    ],
    notes: "85篇，唯物主义哲学"
  },
  {
    title: "潜夫论",
    author: "王符",
    dynasty: "东汉",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《潜夫论笺校正》", era: "现代", notes: "汪继培笺、彭铎校正" },
    ],
    notes: "36篇，政论"
  },
  {
    title: "风俗通义",
    author: "应劭",
    dynasty: "东汉",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《风俗通义校注》", era: "现代", notes: "吴树平" },
    ],
    notes: "10卷，原32篇，今存10篇"
  },
  {
    title: "吴越春秋",
    author: "赵晔",
    dynasty: "东汉",
    category: "史部",
    versions: [
      { type: "现代整理", name: "中华书局《吴越春秋》", era: "现代", notes: "" },
    ],
    notes: "10卷，记吴越争霸"
  },
  {
    title: "越绝书",
    author: "袁康/吴平",
    dynasty: "东汉",
    category: "史部",
    versions: [
      { type: "现代整理", name: "中华书局《越绝书》", era: "现代", notes: "" },
    ],
    notes: "15卷，记吴越史地"
  },

  // ═══════════════════════════════════════════════════════════════
  // 魏晋南北朝典籍
  // ═══════════════════════════════════════════════════════════════
  {
    title: "人物志",
    author: "刘劭",
    dynasty: "曹魏",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《人物志校笺》", era: "现代", notes: "" },
    ],
    notes: "3卷12篇，人才学"
  },
  {
    title: "博物志",
    author: "张华",
    dynasty: "西晋",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《博物志校证》", era: "现代", notes: "范宁" },
    ],
    notes: "10卷，博物学著作"
  },
  {
    title: "搜神记",
    author: "干宝",
    dynasty: "东晋",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《搜神记》", era: "现代", notes: "" },
    ],
    notes: "20卷，志怪小说"
  },
  {
    title: "世说新语",
    author: "刘义庆",
    dynasty: "南朝宋",
    category: "子部",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "" },
      { type: "现代整理", name: "中华书局《世说新语笺疏》", era: "现代", notes: "余嘉锡" },
      { type: "现代整理", name: "中华书局《世说新语校笺》", era: "现代", notes: "徐震堮" },
    ],
    notes: "3卷36门，志人小说"
  },
  {
    title: "文心雕龙",
    author: "刘勰",
    dynasty: "南朝梁",
    category: "集部",
    versions: [
      { type: "现代整理", name: "中华书局《文心雕龙注》", era: "现代", notes: "范文澜" },
      { type: "现代整理", name: "中华书局《文心雕龙义证》", era: "现代", notes: "詹锳" },
    ],
    notes: "10卷50篇，文学理论"
  },
  {
    title: "诗品",
    author: "钟嵘",
    dynasty: "南朝梁",
    category: "集部",
    versions: [
      { type: "现代整理", name: "中华书局《诗品注》", era: "现代", notes: "陈延杰" },
    ],
    notes: "3卷，诗歌评论"
  },
  {
    title: "昭明文选",
    author: "萧统编",
    dynasty: "南朝梁",
    category: "集部",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "" },
      { type: "现代整理", name: "中华书局《文选》", era: "现代", notes: "1977年影印胡刻本" },
      { type: "现代整理", name: "中华书局《文选李善注》", era: "现代", notes: "" },
    ],
    notes: "60卷，最早诗文总集"
  },
  {
    title: "玉台新咏",
    author: "徐陵编",
    dynasty: "南朝陈",
    category: "集部",
    versions: [
      { type: "现代整理", name: "中华书局《玉台新咏笺注》", era: "现代", notes: "吴兆宜" },
    ],
    notes: "10卷，诗歌总集"
  },
  {
    title: "洛阳伽蓝记",
    author: "杨衒之",
    dynasty: "北魏",
    category: "史部",
    versions: [
      { type: "现代整理", name: "中华书局《洛阳伽蓝记校释》", era: "现代", notes: "周祖谟" },
      { type: "现代整理", name: "上海古籍出版社《洛阳伽蓝记》", era: "现代", notes: "" },
    ],
    notes: "5卷，记北魏洛阳佛寺"
  },
  {
    title: "水经注",
    author: "郦道元",
    dynasty: "北魏",
    category: "史部",
    versions: [
      { type: "现代整理", name: "中华书局《水经注校证》", era: "现代", notes: "陈桥驿" },
      { type: "现代整理", name: "江苏古籍出版社《水经注疏》", era: "现代", notes: "杨守敬、熊会贞" },
    ],
    notes: "40卷，地理学名著"
  },
  {
    title: "齐民要术",
    author: "贾思勰",
    dynasty: "北魏",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《齐民要术》", era: "现代", notes: "" },
    ],
    notes: "10卷92篇，农学名著"
  },
  {
    title: "颜氏家训",
    author: "颜之推",
    dynasty: "北齐",
    category: "子部",
    versions: [
      { type: "现代整理", name: "中华书局《颜氏家训集解》", era: "现代", notes: "王利器" },
    ],
    notes: "7卷20篇，家训"
  },
  {
    title: "三十六国春秋",
    author: "崔鸿",
    dynasty: "北魏",
    category: "史部",
    versions: [
      { type: "现代整理", name: "商务印书馆《十六国春秋辑补》", era: "现代", notes: "汤球辑补" },
    ],
    notes: "100卷，记十六国史事"
  },

  // ═══════════════════════════════════════════════════════════════
  // 原有数据（唐至清）
  // ═══════════════════════════════════════════════════════════════
  {
    title: "史记",
    author: "司马迁",
    dynasty: "西汉",
    category: "正史",
    versions: [
      { type: "宋刻本", name: "南宋黄善夫刻本", era: "南宋", notes: "现存最早刻本之一，藏日本" },
      { type: "明刻本", name: "明嘉靖南北监本", era: "明", notes: "国子监刻本，二十四史底本" },
      { type: "清刻本", name: "清武英殿本", era: "清", notes: "乾隆武英殿刻二十四史" },
      { type: "现代整理", name: "中华书局点校本", era: "现代", notes: "1959年，顾颉刚主持" },
    ],
    notes: "二十四史之首，130卷"
  },
  {
    title: "汉书",
    author: "班固",
    dynasty: "东汉",
    category: "正史",
    versions: [
      { type: "宋刻本", name: "北宋监本", era: "北宋", notes: "国子监刻" },
      { type: "明刻本", name: "明毛氏汲古阁本", era: "明", notes: "毛晋刻十七史之一" },
      { type: "清刻本", name: "清武英殿本", era: "清", notes: "" },
      { type: "现代整理", name: "中华书局点校本", era: "现代", notes: "1962年" },
    ],
    notes: "100卷，第一部纪传体断代史"
  },
  {
    title: "后汉书",
    author: "范晔",
    dynasty: "南朝宋",
    category: "正史",
    versions: [
      { type: "宋刻本", name: "宋绍兴刻本", era: "南宋", notes: "" },
      { type: "明刻本", name: "明汲古阁本", era: "明", notes: "" },
      { type: "现代整理", name: "中华书局点校本", era: "现代", notes: "1965年" },
    ],
    notes: "120卷，含志30卷为司马彪撰"
  },
  {
    title: "三国志",
    author: "陈寿",
    dynasty: "西晋",
    category: "正史",
    versions: [
      { type: "宋刻本", name: "宋刻三朝本", era: "南宋", notes: "" },
      { type: "清刻本", name: "清金陵书局本", era: "清", notes: "江南书局刻" },
      { type: "现代整理", name: "中华书局点校本", era: "现代", notes: "1959年，陈乃乾校" },
    ],
    notes: "65卷，裴松之注极重要"
  },
  {
    title: "资治通鉴",
    author: "司马光",
    dynasty: "北宋",
    category: "编年",
    versions: [
      { type: "宋刻本", name: "南宋绍兴二浙东路茶盐司刻本", era: "南宋", notes: "存最早刻本，藏国家图书馆" },
      { type: "清刻本", name: "清胡克家翻刻元本", era: "清", notes: "嘉庆年间" },
      { type: "现代整理", name: "中华书局点校本", era: "现代", notes: "1956年，顾颉刚主持" },
    ],
    notes: "294卷，附考异、目录"
  },
  {
    title: "续资治通鉴长编",
    author: "李焘",
    dynasty: "南宋",
    category: "编年",
    versions: [
      { type: "清刻本", name: "清浙江书局本", era: "清", notes: "" },
      { type: "现代整理", name: "中华书局点校本", era: "现代", notes: "1979年起陆续出版" },
    ],
    notes: "520卷，记北宋九朝史事"
  },
  {
    title: "建炎以来系年要录",
    author: "李心传",
    dynasty: "南宋",
    category: "编年",
    versions: [
      { type: "清刻本", name: "清光绪广雅书局本", era: "清", notes: "" },
      { type: "现代整理", name: "中华书局点校本", era: "现代", notes: "2013年" },
    ],
    notes: "200卷，记南宋高宗朝"
  },
  {
    title: "三朝北盟会编",
    author: "徐梦莘",
    dynasty: "南宋",
    category: "史料汇编",
    versions: [
      { type: "清刻本", name: "清光绪四年刻本", era: "清", notes: "" },
      { type: "现代整理", name: "上海古籍出版社", era: "现代", notes: "1987年影印" },
    ],
    notes: "250卷，徽宗/钦宗/高宗三朝宋金关系"
  },
  {
    title: "文献通考",
    author: "马端临",
    dynasty: "元",
    category: "政书",
    versions: [
      { type: "明刻本", name: "明嘉靖冯天驭刻本", era: "明", notes: "" },
      { type: "清刻本", name: "清武英殿本", era: "清", notes: "" },
      { type: "现代整理", name: "中华书局影印", era: "现代", notes: "1986年" },
    ],
    notes: "348卷，十通之一"
  },
  {
    title: "通典",
    author: "杜佑",
    dynasty: "唐",
    category: "政书",
    versions: [
      { type: "宋刻本", name: "宋刻递修本", era: "南宋", notes: "" },
      { type: "清刻本", name: "清武英殿本", era: "清", notes: "" },
      { type: "现代整理", name: "中华书局点校本", era: "现代", notes: "1988年" },
    ],
    notes: "200卷，十通之首"
  },
  {
    title: "文苑英华",
    author: "李昉等",
    dynasty: "北宋",
    category: "总集",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "残缺" },
      { type: "明刻本", name: "明嘉靖刻本", era: "明", notes: "" },
      { type: "现代整理", name: "中华书局影印", era: "现代", notes: "1966年" },
    ],
    notes: "1000卷，宋四大书之一"
  },
  {
    title: "太平御览",
    author: "李昉等",
    dynasty: "北宋",
    category: "类书",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "北宋", notes: "存残卷" },
      { type: "现代整理", name: "中华书局影印", era: "现代", notes: "1960年" },
    ],
    notes: "1000卷，宋四大书之一"
  },
  {
    title: "册府元龟",
    author: "王钦若等",
    dynasty: "北宋",
    category: "类书",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "北宋", notes: "" },
      { type: "现代整理", name: "中华书局影印", era: "现代", notes: "1960年" },
    ],
    notes: "1000卷，宋四大书之一"
  },
  {
    title: "唐律疏议",
    author: "长孙无忌等",
    dynasty: "唐",
    category: "法律",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "" },
      { type: "现代整理", name: "中华书局点校本", era: "现代", notes: "1983年" },
    ],
    notes: "30卷，现存最早完整法典"
  },
  {
    title: "东京梦华录",
    author: "孟元老",
    dynasty: "南宋",
    category: "笔记",
    versions: [
      { type: "元刻本", name: "元刻本", era: "元", notes: "" },
      { type: "现代整理", name: "中华书局", era: "现代", notes: "多种版本" },
    ],
    notes: "10卷，北宋汴京风俗"
  },
  {
    title: "梦粱录",
    author: "吴自牧",
    dynasty: "南宋",
    category: "笔记",
    versions: [
      { type: "明刻本", name: "明刻本", era: "明", notes: "" },
      { type: "现代整理", name: "浙江人民出版社", era: "现代", notes: "1984年" },
    ],
    notes: "20卷，南宋临安风俗"
  },
  {
    title: "武林旧事",
    author: "周密",
    dynasty: "南宋",
    category: "笔记",
    versions: [
      { type: "明刻本", name: "明刻本", era: "明", notes: "" },
      { type: "现代整理", name: "中华书局", era: "现代", notes: "1982年" },
    ],
    notes: "10卷，南宋杭州风物"
  },
  {
    title: "容斋随笔",
    author: "洪迈",
    dynasty: "南宋",
    category: "笔记",
    versions: [
      { type: "宋刻本", name: "宋刻本", era: "南宋", notes: "" },
      { type: "现代整理", name: "中华书局", era: "现代", notes: "2005年" },
    ],
    notes: "74卷，五笔合集"
  },
  {
    title: "历代名臣奏议",
    author: "黄淮等",
    dynasty: "明",
    category: "史料汇编",
    versions: [
      { type: "明刻本", name: "明永乐内府刻本", era: "明", notes: "" },
      { type: "现代整理", name: "上海古籍出版社", era: "现代", notes: "1989年影印" },
    ],
    notes: "350卷"
  },
  {
    title: "宋会要辑稿",
    author: "徐松辑",
    dynasty: "清",
    category: "政书",
    versions: [
      { type: "清稿本", name: "清徐松原稿", era: "清", notes: "" },
      { type: "现代整理", name: "中华书局影印", era: "现代", notes: "1957年" },
    ],
    notes: "366卷，从《永乐大典》辑出"
  },
];

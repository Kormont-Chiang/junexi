/**
 * 避讳数据库 · 历代帝讳与替代字
 * 格式: { dynasty, emperor, name, tabooChars, alternatives, notes }
 * 覆盖范围：商周至清
 */
const TABOO_DB = [
  // ── 商 ──
  { dynasty: "商", emperor: "成汤", name: "子履/天乙", tabooChars: "履", alternatives: "无", notes: "商代避讳不严，甲骨文未见避讳" },
  { dynasty: "商", emperor: "盘庚", name: "子旬", tabooChars: "旬", alternatives: "无", notes: "" },
  { dynasty: "商", emperor: "武丁", name: "子昭", tabooChars: "昭", alternatives: "无", notes: "" },
  { dynasty: "商", emperor: "帝辛", name: "子受/纣", tabooChars: "受,纣", alternatives: "无", notes: "" },

  // ── 西周 ──
  { dynasty: "西周", emperor: "文王", name: "姬昌", tabooChars: "昌", alternatives: "无", notes: "周代避讳制度萌芽，不严" },
  { dynasty: "西周", emperor: "武王", name: "姬发", tabooChars: "发", alternatives: "无", notes: "" },
  { dynasty: "西周", emperor: "成王", name: "姬诵", tabooChars: "诵", alternatives: "无", notes: "" },
  { dynasty: "西周", emperor: "康王", name: "姬钊", tabooChars: "钊", alternatives: "无", notes: "" },
  { dynasty: "西周", emperor: "昭王", name: "姬瑕", tabooChars: "瑕", alternatives: "无", notes: "" },
  { dynasty: "西周", emperor: "穆王", name: "姬满", tabooChars: "满", alternatives: "无", notes: "" },
  { dynasty: "西周", emperor: "厉王", name: "姬胡", tabooChars: "胡", alternatives: "无", notes: "" },
  { dynasty: "西周", emperor: "宣王", name: "姬静", tabooChars: "静", alternatives: "无", notes: "" },

  // ── 东周/春秋战国 ──
  { dynasty: "东周", emperor: "平王", name: "姬宜臼", tabooChars: "宜,臼", alternatives: "无", notes: "春秋战国避讳更松弛" },
  { dynasty: "东周", emperor: "桓王", name: "姬林", tabooChars: "林", alternatives: "无", notes: "" },

  // ── 秦 ──
  { dynasty: "秦", emperor: "始皇帝", name: "嬴政", tabooChars: "政", alternatives: "无", notes: "秦避讳不严格，始皇帝未大规模避讳" },
  { dynasty: "秦", emperor: "始皇帝", name: "嬴政", tabooChars: "朕", alternatives: "无", notes: "天子自称朕，但并非避讳字" },
  { dynasty: "秦", emperor: "二世", name: "胡亥", tabooChars: "亥", alternatives: "无", notes: "" },

  // ── 西汉 ──
  { dynasty: "西汉", emperor: "高祖", name: "刘邦", tabooChars: "邦", alternatives: "国/封", notes: "邦→国，如「安邦」→「安国」" },
  { dynasty: "西汉", emperor: "惠帝", name: "刘盈", tabooChars: "盈", alternatives: "满/溢", notes: "盈→满，如「盈川」→「满川」" },
  { dynasty: "西汉", emperor: "文帝", name: "刘恒", tabooChars: "恒", alternatives: "常/镇", notes: "恒山→常山；恒州→镇州" },
  { dynasty: "西汉", emperor: "景帝", name: "刘启", tabooChars: "启", alternatives: "开/荊", notes: "启封→开封；启蛰→惊蛰" },
  { dynasty: "西汉", emperor: "武帝", name: "刘彻", tabooChars: "彻", alternatives: "通/撤", notes: "彻侯→通侯；蒯彻→蒯通" },
  { dynasty: "西汉", emperor: "昭帝", name: "刘弗陵", tabooChars: "弗,陵", alternatives: "无", notes: "" },
  { dynasty: "西汉", emperor: "宣帝", name: "刘询", tabooChars: "询", alternatives: "谋/谘", notes: "荀卿→孙卿（一说避汉宣帝讳）" },
  { dynasty: "西汉", emperor: "元帝", name: "刘奭", tabooChars: "奭", alternatives: "盛/硕", notes: "" },
  { dynasty: "西汉", emperor: "成帝", name: "刘骜", tabooChars: "骜", alternatives: "无", notes: "" },
  { dynasty: "西汉", emperor: "哀帝", name: "刘欣", tabooChars: "欣", alternatives: "喜/怡", notes: "欣→喜" },
  { dynasty: "西汉", emperor: "平帝", name: "刘衎", tabooChars: "衎", alternatives: "无", notes: "" },

  // ── 东汉 ──
  { dynasty: "东汉", emperor: "光武帝", name: "刘秀", tabooChars: "秀", alternatives: "茂/稜", notes: "秀→茂" },
  { dynasty: "东汉", emperor: "明帝", name: "刘庄", tabooChars: "庄", alternatives: "严/荘", notes: "庄→严；庄子→严子（后复）" },
  { dynasty: "东汉", emperor: "章帝", name: "刘炟", tabooChars: "炟", alternatives: "无", notes: "" },
  { dynasty: "东汉", emperor: "和帝", name: "刘肇", tabooChars: "肇", alternatives: "始/元", notes: "" },
  { dynasty: "东汉", emperor: "殇帝", name: "刘隆", tabooChars: "隆", alternatives: "盛/兴", notes: "隆→盛" },
  { dynasty: "东汉", emperor: "安帝", name: "刘祜", tabooChars: "祜", alternatives: "无", notes: "" },
  { dynasty: "东汉", emperor: "顺帝", name: "刘保", tabooChars: "保", alternatives: "无", notes: "" },
  { dynasty: "东汉", emperor: "桓帝", name: "刘志", tabooChars: "志", alternatives: "无", notes: "" },
  { dynasty: "东汉", emperor: "灵帝", name: "刘宏", tabooChars: "宏", alternatives: "无", notes: "" },

  // ── 三国 ──
  // 曹魏
  { dynasty: "曹魏", emperor: "武帝", name: "曹操", tabooChars: "操", alternatives: "无", notes: "曹操死后避讳不严格" },
  { dynasty: "曹魏", emperor: "文帝", name: "曹丕", tabooChars: "丕", alternatives: "无", notes: "" },
  { dynasty: "曹魏", emperor: "明帝", name: "曹叡", tabooChars: "叡", alternatives: "睿", notes: "" },
  // 蜀汉
  { dynasty: "蜀汉", emperor: "昭烈帝", name: "刘备", tabooChars: "备", alternatives: "无", notes: "" },
  { dynasty: "蜀汉", emperor: "后主", name: "刘禅", tabooChars: "禅", alternatives: "无", notes: "" },
  // 孙吴
  { dynasty: "孙吴", emperor: "大帝", name: "孙权", tabooChars: "权", alternatives: "无", notes: "" },
  { dynasty: "孙吴", emperor: "末帝", name: "孙皓", tabooChars: "皓", alternatives: "无", notes: "" },

  // ── 西晋 ──
  { dynasty: "西晋", emperor: "武帝", name: "司马炎", tabooChars: "炎", alternatives: "无", notes: "" },
  { dynasty: "西晋", emperor: "惠帝", name: "司马衷", tabooChars: "衷", alternatives: "无", notes: "" },
  { dynasty: "西晋", emperor: "怀帝", name: "司马炽", tabooChars: "炽", alternatives: "无", notes: "" },
  { dynasty: "西晋", emperor: "愍帝", name: "司马邺", tabooChars: "邺", alternatives: "无", notes: "" },

  // ── 东晋 ──
  { dynasty: "东晋", emperor: "元帝", name: "司马睿", tabooChars: "睿", alternatives: "无", notes: "" },
  { dynasty: "东晋", emperor: "明帝", name: "司马绍", tabooChars: "绍", alternatives: "无", notes: "" },
  { dynasty: "东晋", emperor: "成帝", name: "司马衍", tabooChars: "衍", alternatives: "无", notes: "" },
  { dynasty: "东晋", emperor: "康帝", name: "司马岳", tabooChars: "岳", alternatives: "无", notes: "" },
  { dynasty: "东晋", emperor: "穆帝", name: "司马聃", tabooChars: "聃", alternatives: "无", notes: "" },
  { dynasty: "东晋", emperor: "哀帝", name: "司马丕", tabooChars: "丕", alternatives: "无", notes: "" },
  { dynasty: "东晋", emperor: "简文帝", name: "司马昱", tabooChars: "昱", alternatives: "无", notes: "" },
  { dynasty: "东晋", emperor: "孝武帝", name: "司马曜", tabooChars: "曜", alternatives: "无", notes: "" },
  { dynasty: "东晋", emperor: "安帝", name: "司马德宗", tabooChars: "宗", alternatives: "无", notes: "" },

  // ── 南朝宋 ──
  { dynasty: "南朝宋", emperor: "武帝", name: "刘裕", tabooChars: "裕", alternatives: "无", notes: "" },
  { dynasty: "南朝宋", emperor: "文帝", name: "刘义隆", tabooChars: "义,隆", alternatives: "无", notes: "" },
  { dynasty: "南朝宋", emperor: "孝武帝", name: "刘骏", tabooChars: "骏", alternatives: "无", notes: "" },
  { dynasty: "南朝宋", emperor: "明帝", name: "刘彧", tabooChars: "彧", alternatives: "无", notes: "" },

  // ── 南朝齐 ──
  { dynasty: "南朝齐", emperor: "高帝", name: "萧道成", tabooChars: "道,成", alternatives: "无", notes: "" },
  { dynasty: "南朝齐", emperor: "武帝", name: "萧赜", tabooChars: "赜", alternatives: "无", notes: "" },

  // ── 南朝梁 ──
  { dynasty: "南朝梁", emperor: "武帝", name: "萧衍", tabooChars: "衍", alternatives: "无", notes: "" },
  { dynasty: "南朝梁", emperor: "简文帝", name: "萧纲", tabooChars: "纲", alternatives: "无", notes: "" },
  { dynasty: "南朝梁", emperor: "元帝", name: "萧绎", tabooChars: "绎", alternatives: "无", notes: "" },

  // ── 南朝陈 ──
  { dynasty: "南朝陈", emperor: "武帝", name: "陈霸先", tabooChars: "霸,先", alternatives: "无", notes: "" },
  { dynasty: "南朝陈", emperor: "文帝", name: "陈蒨", tabooChars: "蒨", alternatives: "无", notes: "" },

  // ── 北魏 ──
  { dynasty: "北魏", emperor: "道武帝", name: "拓跋珪", tabooChars: "珪", alternatives: "无", notes: "" },
  { dynasty: "北魏", emperor: "明元帝", name: "拓跋嗣", tabooChars: "嗣", alternatives: "无", notes: "" },
  { dynasty: "北魏", emperor: "太武帝", name: "拓跋焘", tabooChars: "焘", alternatives: "无", notes: "" },
  { dynasty: "北魏", emperor: "文成帝", name: "拓跋濬", tabooChars: "濬", alternatives: "无", notes: "" },
  { dynasty: "北魏", emperor: "献文帝", name: "拓跋弘", tabooChars: "弘", alternatives: "宏", notes: "" },
  { dynasty: "北魏", emperor: "孝文帝", name: "元宏", tabooChars: "宏", alternatives: "无", notes: "改姓元后，拓跋宏→元宏" },
  { dynasty: "北魏", emperor: "宣武帝", name: "元恪", tabooChars: "恪", alternatives: "无", notes: "" },
  { dynasty: "北魏", emperor: "孝明帝", name: "元诩", tabooChars: "诩", alternatives: "无", notes: "" },
  { dynasty: "北魏", emperor: "孝庄帝", name: "元子攸", tabooChars: "攸", alternatives: "无", notes: "" },

  // ── 北齐 ──
  { dynasty: "北齐", emperor: "文宣帝", name: "高洋", tabooChars: "洋", alternatives: "无", notes: "" },
  { dynasty: "北齐", emperor: "武成帝", name: "高湛", tabooChars: "湛", alternatives: "无", notes: "" },

  // ── 北周 ──
  { dynasty: "北周", emperor: "武帝", name: "宇文邕", tabooChars: "邕", alternatives: "无", notes: "" },
  { dynasty: "北周", emperor: "宣帝", name: "宇文赟", tabooChars: "赟", alternatives: "无", notes: "" },

  // ── 隋 ──
  { dynasty: "隋", emperor: "文帝", name: "杨坚", tabooChars: "坚", alternatives: "无", notes: "" },
  { dynasty: "隋", emperor: "炀帝", name: "杨广", tabooChars: "广", alternatives: "无", notes: "" },
  { dynasty: "隋", emperor: "恭帝", name: "杨侑", tabooChars: "侑", alternatives: "无", notes: "" },

  // ── 唐 ──
  { dynasty: "唐", emperor: "高祖", name: "李渊", tabooChars: "渊", alternatives: "泉/深/淵(缺笔)", notes: "改渊为泉，如陶渊明→陶泉明" },
  { dynasty: "唐", emperor: "太宗", name: "李世民", tabooChars: "世,民", alternatives: "代/系/人/氏/户", notes: "观世音→观音；民部→户部" },
  { dynasty: "唐", emperor: "高宗", name: "李治", tabooChars: "治", alternatives: "理/持/化", notes: "治书侍御史→持书侍御史" },
  { dynasty: "唐", emperor: "中宗", name: "李显", tabooChars: "显", alternatives: "明", notes: "后改名李哲" },
  { dynasty: "唐", emperor: "睿宗", name: "李旦", tabooChars: "旦", alternatives: "明/旭", notes: "" },
  { dynasty: "唐", emperor: "玄宗", name: "李隆基", tabooChars: "隆,基", alternatives: "盛/兴", notes: "隆州→阆州；大基山→大基(真)山" },
  { dynasty: "唐", emperor: "肃宗", name: "李亨", tabooChars: "亨", alternatives: "通/嘉", notes: "亨州→嘉州" },
  { dynasty: "唐", emperor: "代宗", name: "李豫", tabooChars: "豫", alternatives: "预/舒", notes: "豫章郡→章郡(后复)" },
  { dynasty: "唐", emperor: "德宗", name: "李适", tabooChars: "适", alternatives: "敌/的", notes: "音kuò，与適不同字但常混" },
  { dynasty: "唐", emperor: "宪宗", name: "李纯", tabooChars: "纯", alternatives: "淳/允", notes: "纯州→峿州" },
  { dynasty: "唐", emperor: "穆宗", name: "李恒", tabooChars: "恒", alternatives: "常/镇", notes: "恒州→镇州；恒山→常山" },
  { dynasty: "唐", emperor: "敬宗", name: "李湛", tabooChars: "湛", alternatives: "澄/覃", notes: "" },
  { dynasty: "唐", emperor: "文宗", name: "李昂", tabooChars: "昂", alternatives: "昻/仰", notes: "" },
  { dynasty: "唐", emperor: "武宗", name: "李炎", tabooChars: "炎", alternatives: "淡/燄", notes: "" },
  { dynasty: "唐", emperor: "宣宗", name: "李忱", tabooChars: "忱", alternatives: "谌/氏", notes: "" },
  { dynasty: "唐", emperor: "懿宗", name: "李漼", tabooChars: "漼", alternatives: "璀/崔", notes: "" },
  { dynasty: "唐", emperor: "僖宗", name: "李儇", tabooChars: "儇", alternatives: "喧/宣", notes: "" },
  { dynasty: "唐", emperor: "昭宗", name: "李晔", tabooChars: "晔", alternatives: "烨/耀", notes: "" },
  // 宋
  { dynasty: "北宋", emperor: "太祖", name: "赵匡胤", tabooChars: "匡,胤", alternatives: "正/规/裔", notes: "匡义→光义；胤山→商山" },
  { dynasty: "北宋", emperor: "太宗", name: "赵炅", tabooChars: "炅,光,义", alternatives: "炯/煦", notes: "本名匡义，即位改炅" },
  { dynasty: "北宋", emperor: "真宗", name: "赵恒", tabooChars: "恒", alternatives: "常/镇", notes: "恒山→常山" },
  { dynasty: "北宋", emperor: "仁宗", name: "赵祯", tabooChars: "祯", alternatives: "祥/祺", notes: "祯州→惠州；文徵明→文征明" },
  { dynasty: "北宋", emperor: "英宗", name: "赵曙", tabooChars: "曙", alternatives: "晓/树", notes: "曙州→筠州" },
  { dynasty: "北宋", emperor: "神宗", name: "赵顼", tabooChars: "顼", alternatives: "旭/煦", notes: "" },
  { dynasty: "北宋", emperor: "哲宗", name: "赵煦", tabooChars: "煦", alternatives: "昫/煦(缺笔)", notes: "" },
  { dynasty: "北宋", emperor: "徽宗", name: "赵佶", tabooChars: "佶", alternatives: "吉/诘", notes: "" },
  { dynasty: "北宋", emperor: "钦宗", name: "赵桓", tabooChars: "桓", alternatives: "垣/恒", notes: "" },
  { dynasty: "南宋", emperor: "高宗", name: "赵构", tabooChars: "构", alternatives: "彀/姤", notes: "构→彀" },
  { dynasty: "南宋", emperor: "孝宗", name: "赵昚", tabooChars: "昚", alternatives: "慎/缜", notes: "初名伯琮" },
  { dynasty: "南宋", emperor: "光宗", name: "赵惇", tabooChars: "惇", alternatives: "敦/淳", notes: "" },
  { dynasty: "南宋", emperor: "宁宗", name: "赵扩", tabooChars: "扩", alternatives: "廓/彉", notes: "" },
  { dynasty: "南宋", emperor: "理宗", name: "赵昀", tabooChars: "昀", alternatives: "匀/盷", notes: "初名赵与莒" },
  { dynasty: "南宋", emperor: "度宗", name: "赵禥", tabooChars: "禥", alternatives: "基/祺", notes: "初名赵孟启" },
  // 元
  { dynasty: "元", emperor: "世祖", name: "忽必烈", tabooChars: "必,烈", alternatives: "无", notes: "元代避讳不严，但刻本偶有缺笔" },
  // 明
  { dynasty: "明", emperor: "太祖", name: "朱元璋", tabooChars: "元,璋", alternatives: "原/玄", notes: "元→原；玄→元" },
  { dynasty: "明", emperor: "成祖", name: "朱棣", tabooChars: "棣", alternatives: "逮/递", notes: "" },
  { dynasty: "明", emperor: "仁宗", name: "朱高炽", tabooChars: "炽", alternatives: "熾(缺笔)", notes: "" },
  { dynasty: "明", emperor: "宣宗", name: "朱瞻基", tabooChars: "瞻,基", alternatives: "詹/居", notes: "" },
  { dynasty: "明", emperor: "英宗", name: "朱祁镇", tabooChars: "祁,镇", alternatives: "祺/振", notes: "" },
  { dynasty: "明", emperor: "宪宗", name: "朱见深", tabooChars: "见,深", alternatives: "现/深(缺笔)", notes: "见→现" },
  { dynasty: "明", emperor: "孝宗", name: "朱祐樘", tabooChars: "祐,樘", alternatives: "佑/堂", notes: "" },
  { dynasty: "明", emperor: "世宗", name: "朱厚熜", tabooChars: "熜", alternatives: "匆/聪", notes: "" },
  { dynasty: "明", emperor: "穆宗", name: "朱载坖", tabooChars: "坖", alternatives: "垕", notes: "原名载垕" },
  { dynasty: "明", emperor: "神宗", name: "朱翊钧", tabooChars: "翊,钧", alternatives: "翌/均", notes: "" },
  { dynasty: "明", emperor: "光宗", name: "朱常洛", tabooChars: "常,洛", alternatives: "尝/雒", notes: "" },
  { dynasty: "明", emperor: "熹宗", name: "朱由校", tabooChars: "校", alternatives: "较/挍", notes: "" },
  { dynasty: "明", emperor: "思宗", name: "朱由检", tabooChars: "检", alternatives: "简/拣", notes: "" },
  // 清
  { dynasty: "清", emperor: "世祖", name: "福临", tabooChars: "临", alternatives: "林/淋", notes: "" },
  { dynasty: "清", emperor: "圣祖", name: "玄烨", tabooChars: "玄,烨", alternatives: "元/煜", notes: "玄→元；李玄霸→李元霸" },
  { dynasty: "清", emperor: "世宗", name: "胤禛", tabooChars: "胤,禛", alternatives: "允/祯", notes: "胤→允；兄弟改名允X" },
  { dynasty: "清", emperor: "高宗", name: "弘历", tabooChars: "弘,历", alternatives: "宏/厤", notes: "弘→宏；历→厤" },
  { dynasty: "清", emperor: "仁宗", name: "颙琰", tabooChars: "琰", alternatives: "瑗/琬", notes: "初名永琰" },
  { dynasty: "清", emperor: "宣宗", name: "旻宁", tabooChars: "旻,宁", alternatives: "民/甯", notes: "初名绵宁" },
  { dynasty: "清", emperor: "文宗", name: "奕詝", tabooChars: "詝", alternatives: "宁/伫", notes: "" },
  { dynasty: "清", emperor: "穆宗", name: "载淳", tabooChars: "淳", alternatives: "醇/湻", notes: "" },
  { dynasty: "清", emperor: "德宗", name: "载湉", tabooChars: "湉", alternatives: "恬/甜", notes: "" },
  { dynasty: "清", emperor: "溥仪", name: "溥仪", tabooChars: "仪", alternatives: "宜/沂", notes: "清末避讳已松弛" },
];

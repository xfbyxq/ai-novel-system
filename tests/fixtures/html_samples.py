"""Mock HTML 样本数据，用于单元测试解析方法。"""

# 模拟起点排行榜页面 HTML
# 注意：只使用 .book-mid-info 选择器，避免与 .rank-list li 重复匹配
RANKING_PAGE_HTML = """
<html>
<body>
<div class="ranking-container">
  <div class="book-mid-info">
    <h2><a href="/book/1038710110/">星域求生：我能看见提示</a></h2>
    <div class="author">
      <a class="author-name" href="/author/1234/">孤独的飞鸟</a>
      <span>科幻</span>
    </div>
    <div class="intro">末世来临，人类只能在星域中求生...</div>
    <div class="total">
      <span>150万字</span>
    </div>
    <span class="tag">末世</span>
    <span class="tag">星际</span>
    <span class="tag">系统</span>
  </div>
  <div class="book-mid-info">
    <h2><a href="/book/1039123456/">仙道长青</a></h2>
    <div class="author">
      <a class="author-name" href="/author/5678/">林中有风</a>
      <span>仙侠</span>
    </div>
    <div class="intro">修仙之路，长生不老...</div>
    <div class="total">
      <span>80.5万字</span>
    </div>
    <span class="tag">修仙</span>
    <span class="tag">长生</span>
  </div>
  <div class="book-mid-info">
    <h2><a href="/book/1040999888/">都市之无敌归来</a></h2>
    <div class="author">
      <a class="author-name" href="/author/9012/">笑看风云</a>
      <span>都市</span>
    </div>
    <div class="intro">十年归来，他已站在巅峰...</div>
    <div class="total">
      <span>320000字</span>
    </div>
    <span class="tag">都市</span>
  </div>
</div>
</body>
</html>
"""

# 模拟标签页 HTML
TAGS_PAGE_HTML = """
<html>
<body>
<div class="tag-list">
  <a href="/tag/xuanhuan/">玄幻</a>
  <a href="/tag/qihuan/">奇幻</a>
  <a href="/tag/wuxia/">武侠</a>
  <a href="/tag/xianxia/">仙侠</a>
  <a href="/tag/dushi/">都市</a>
</div>
<div class="work-filter">
  <a href="/filter/hot/">热血</a>
  <a href="/filter/sys/">系统</a>
</div>
</body>
</html>
"""

# 模拟书籍详情页 HTML
BOOK_DETAIL_HTML = """
<html>
<body>
<div class="book-info">
  <h1><em>测试之书：无尽征途</em></h1>
  <div class="writer"><a href="/author/1234/">青衫墨客</a></div>
  <div class="book-intro"><p>这是一个关于冒险与成长的故事...</p></div>
  <div class="tag">
    <a href="/tag/xuanhuan/">玄幻</a>
    <a href="/tag/maoxian/">冒险</a>
    <a href="/tag/chengzhang/">成长</a>
  </div>
</div>
</body>
</html>
"""

# 模拟分类页 HTML
GENRES_PAGE_HTML = """
<html>
<body>
<div class="channel-nav">
  <a href="/all/">全部</a>
  <a href="/xuanhuan/">玄幻</a>
  <a href="/qihuan/">奇幻</a>
  <a href="/wuxia/">武侠</a>
  <a href="/xianxia/">仙侠</a>
  <a href="/dushi/">都市</a>
  <a href="/lishi/">历史</a>
  <a href="/youxi/">游戏</a>
  <a href="/kehuan/">科幻</a>
</div>
<div class="select-list">
  <a href="/all-work/">全部作品</a>
  <a href="/xuanhuan-work/">玄幻奇幻</a>
  <a href="/wuxia-work/">武侠仙侠</a>
</div>
</body>
</html>
"""

# 空页面（边缘情况）
EMPTY_PAGE_HTML = """
<html>
<body>
<div class="empty-content">没有找到结果</div>
</body>
</html>
"""

# 部分字段缺失的排行榜条目
PARTIAL_DATA_HTML = """
<html>
<body>
<div class="ranking-container">
  <div class="book-mid-info">
    <h2><a href="/book/9999999999/">只有标题的书</a></h2>
  </div>
</div>
</body>
</html>
"""

param(
  [string]$StartUrl = "https://www.deeplearningbook.org/",
  [string]$OutDir = "D:\ic\master project\project_code\KG_construction\resource"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
$domain = "www.deeplearningbook.org"
$pdfDir = Join-Path $OutDir "pdf"
New-Item -ItemType Directory -Force -Path $pdfDir | Out-Null

function Get-Bytes([string]$url) {
  $req = [System.Net.HttpWebRequest]::Create($url)
  $req.UserAgent = "Mozilla/5.0 Codex academic-resource-crawler"
  $req.Timeout = 15000
  $req.ReadWriteTimeout = 15000
  $req.AllowAutoRedirect = $true
  $resp = $req.GetResponse()
  try {
    $ms = New-Object System.IO.MemoryStream
    $stream = $resp.GetResponseStream()
    $buffer = New-Object byte[] 8192
    while (($read = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) { $ms.Write($buffer, 0, $read) }
    return @{ Bytes = $ms.ToArray(); ContentType = $resp.ContentType; Status = 200 }
  } finally { $resp.Close() }
}
function Normalize-Url([string]$base, [string]$href) {
  if ([string]::IsNullOrWhiteSpace($href)) { return $null }
  $href = $href.Trim()
  if ($href.StartsWith("#") -or $href.StartsWith("mailto:") -or $href.StartsWith("javascript:") -or $href.StartsWith("tel:")) { return $null }
  try { $u = New-Object System.Uri ((New-Object System.Uri $base), $href); $b = New-Object System.UriBuilder $u; $b.Fragment = ""; return $b.Uri.AbsoluteUri } catch { return $null }
}
function Safe-Name([string]$url, [string]$fallbackExt) {
  $u = New-Object System.Uri $url
  $leaf = [System.IO.Path]::GetFileName($u.AbsolutePath)
  if ([string]::IsNullOrWhiteSpace($leaf)) { $leaf = "index$fallbackExt" }
  $leaf = [System.Net.WebUtility]::UrlDecode($leaf)
  foreach ($c in [System.IO.Path]::GetInvalidFileNameChars()) { $leaf = $leaf.Replace($c, '_') }
  if (-not [System.IO.Path]::GetExtension($leaf) -and $fallbackExt) { $leaf += $fallbackExt }
  return $leaf
}

$queue = New-Object 'System.Collections.Generic.Queue[string]'
$seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
$pdfSeen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
$pages = New-Object System.Collections.Generic.List[object]
$pdfs = New-Object System.Collections.Generic.List[object]
$edges = New-Object System.Collections.Generic.List[object]
$linkPattern = '(?is)<a\s+[^>]*href\s*=\s*(["''])(.*?)\1'
$queue.Enqueue($StartUrl)

while ($queue.Count -gt 0 -and $seen.Count -lt 150) {
  $url = $queue.Dequeue()
  if (-not $seen.Add($url)) { continue }
  try {
    $result = Get-Bytes $url
    $ct = [string]$result.ContentType
    if ($ct.Contains("application/pdf") -or $url.ToLowerInvariant().EndsWith(".pdf")) { continue }
    if (-not $ct.Contains("text/html")) { $pages.Add([pscustomobject]@{url=$url; status=200; title=""; content_type=$ct; note="non-html"}); continue }
    $html = [System.Text.Encoding]::UTF8.GetString($result.Bytes)
    $title = ""
    if ($html -match "(?is)<title[^>]*>(.*?)</title>") { $title = ([System.Net.WebUtility]::HtmlDecode($matches[1]) -replace "\s+", " ").Trim() }
    $pages.Add([pscustomobject]@{url=$url; status=200; title=$title; content_type=$ct; note="html"})
    foreach ($m in [regex]::Matches($html, $linkPattern)) {
      $next = Normalize-Url $url $m.Groups[2].Value
      if (-not $next) { continue }
      $nextUri = New-Object System.Uri $next
      if ($nextUri.AbsolutePath.ToLowerInvariant().EndsWith(".pdf")) {
        $edges.Add([pscustomobject]@{from=$url; to=$next; kind="pdf"})
        if ($pdfSeen.Add($next)) {
          $name = Safe-Name $next ".pdf"
          $path = Join-Path $pdfDir $name
          if (Test-Path -Path $path) { $pdfs.Add([pscustomobject]@{url=$next; local_file=$path; status="already_exists"}); continue }
          try { $pdfData = Get-Bytes $next; [System.IO.File]::WriteAllBytes($path, $pdfData.Bytes); $pdfs.Add([pscustomobject]@{url=$next; local_file=$path; status="downloaded"}) }
          catch { $pdfs.Add([pscustomobject]@{url=$next; local_file=""; status=("error: " + $_.Exception.Message)}) }
        }
      } elseif ($nextUri.Host -ieq $domain) {
        $edges.Add([pscustomobject]@{from=$url; to=$next; kind="html"})
        if (-not $seen.Contains($next)) { $queue.Enqueue($next) }
      } else { $edges.Add([pscustomobject]@{from=$url; to=$next; kind="external"}) }
    }
  } catch { $pages.Add([pscustomobject]@{url=$url; status=0; title=""; content_type=""; note=("error: " + $_.Exception.Message)}) }
}

$existingPdfRows = Get-ChildItem -Path $pdfDir -Filter *.pdf | Sort-Object Name | ForEach-Object { [pscustomobject]@{ file=$_.FullName; name=$_.Name; bytes=$_.Length } }
$pagesPath = Join-Path $OutDir "deeplearningbook_pages.csv"
$pdfsPath = Join-Path $OutDir "deeplearningbook_pdfs.csv"
$edgesPath = Join-Path $OutDir "deeplearningbook_links.csv"
$mdPath = Join-Path $OutDir "deeplearningbook_index.md"
$pages | Sort-Object url | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $pagesPath
$pdfs | Sort-Object url | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $pdfsPath
$edges | Sort-Object from,to | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $edgesPath
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# Deep Learning Book crawl index")
$lines.Add("")
$lines.Add("Start URL: $StartUrl")
$lines.Add("Crawled at: $((Get-Date).ToString('s'))")
$lines.Add("")
$lines.Add("## Summary")
$lines.Add("")
$lines.Add("- HTML/pages crawled: $($pages.Count)")
$lines.Add("- PDF links discovered this run: $($pdfs.Count)")
$lines.Add("- PDF files currently in pdf folder: $($existingPdfRows.Count)")
$lines.Add("- Link edges recorded: $($edges.Count)")
$lines.Add("")
$lines.Add("## Existing PDF Files")
$lines.Add("")
foreach ($p in $existingPdfRows) { $lines.Add("- `$($p.file)` ($($p.bytes) bytes)") }
$lines.Add("")
$lines.Add("## Crawled Pages")
$lines.Add("")
foreach ($p in ($pages | Sort-Object url)) { $label = if ($p.title) { $p.title } else { $p.url }; $lines.Add("- [$label]($($p.url))") }
[System.IO.File]::WriteAllLines($mdPath, $lines, (New-Object System.Text.UTF8Encoding $false))
[pscustomobject]@{ pages=$pages.Count; pdf_links=$pdfs.Count; pdf_files=$existingPdfRows.Count; links=$edges.Count; index=$mdPath; pages_csv=$pagesPath; pdfs_csv=$pdfsPath; links_csv=$edgesPath } | ConvertTo-Json -Depth 4

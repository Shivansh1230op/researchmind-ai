import {test,expect} from "@playwright/test";
test.beforeEach(async({page})=>{
 await page.route("**/api/**",async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith("/auth/me"))return route.fulfill({json:{id:"test",name:"Ada Lovelace",email:"ada@example.com"}});
  if(path.endsWith("/workspaces"))return route.fulfill({json:[{id:"test-workspace",name:"AI research",documents:0}]});
  if(path.endsWith("/documents"))return route.fulfill({json:{documents:[],total:0}});
  if(path.endsWith("/chat/history"))return route.fulfill({json:{messages:[],total:0}});
  if(path.endsWith("/analytics/overview"))return route.fulfill({json:{documents:0,questions:0,sessions:0,chunks:0,storage_bytes:0,success_rate:null,activity:[]}});
  return route.fulfill({json:[]});
 });
});
test("dashboard and command search work",async({page})=>{
 await page.setViewportSize({width:1440,height:1050});
 await page.goto("/dashboard");await expect(page.getByRole("heading",{name:/Welcome back, Ada/})).toBeVisible();
 await expect(page.locator(".metric-card").last()).toHaveCSS("opacity","1");
 await page.screenshot({path:"../docs/screenshots/overview.png",fullPage:true});
 await page.keyboard.press("Control+k");await expect(page.getByRole("dialog",{name:"Search documents"})).toBeVisible();
 await page.getByPlaceholder("Find a document…").fill("missing");await expect(page.getByText("No matching documents. Upload a paper to begin.")).toBeVisible();
 await page.keyboard.press("Escape");await expect(page.getByRole("dialog")).toHaveCount(0);
});
test("workspace shows honest empty states",async({page})=>{
 await page.setViewportSize({width:1440,height:950});
 await page.goto("/dashboard/workspace");await expect(page.getByText("Big questions.")).toBeVisible();
 await page.screenshot({path:"../docs/screenshots/workspace.png",fullPage:true});
 await expect(page.getByRole("button",{name:"Send question"})).toBeDisabled();
 await page.getByRole("combobox",{name:"Research mode"}).selectOption("critical");
 await expect(page.getByRole("combobox",{name:"Research mode"})).toHaveValue("critical");
});
test("mobile sources and document panels remain accessible",async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto("/dashboard/workspace");
 await page.getByRole("button",{name:"Documents",exact:true}).click();await expect(page.getByText("Drop files or click to upload")).toBeVisible();
 await page.getByRole("button",{name:"Done",exact:true}).click();
 await page.getByRole("button",{name:"Sources",exact:true}).click();await expect(page.getByRole("heading",{name:"Evidence lives here."})).toBeVisible();
 await page.getByRole("button",{name:"Done",exact:true}).click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});
test("login exposes registration and validation",async({page})=>{
 await page.goto("/login");await page.getByRole("button",{name:"New to ResearchMind? Create an account"}).click();
 await expect(page.getByRole("heading",{name:"Make room for better ideas."})).toBeVisible();
 await expect(page.getByLabel("Your name")).toBeVisible();await expect(page.getByLabel("Password",{exact:true})).toHaveAttribute("minlength","10");
});

test("polished dashboard supports light theme, reduced motion and mobile",async({page})=>{
 await page.emulateMedia({reducedMotion:"reduce"});
 await page.goto("/dashboard");
 await expect(page.getByRole("heading",{name:/Welcome back, Ada/})).toBeVisible();
 await expect(page.locator(".constellation-core")).toHaveCSS("animation-name","none");
 await page.getByRole("button",{name:"Toggle theme"}).click();
 await expect(page.locator("html")).toHaveAttribute("data-theme","light");
 await page.screenshot({path:"../docs/screenshots/overview-light.png",fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await expect(page.getByRole("heading",{name:/Welcome back, Ada/})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 await page.screenshot({path:"../docs/screenshots/overview-mobile.png",fullPage:true});
});

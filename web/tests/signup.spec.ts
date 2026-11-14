import {test,expect} from "@playwright/test";
test("signup requests OTP and handles incorrect verification",async({page})=>{
 await page.route("**/api/auth/register",async route=>{const body=route.request().postDataJSON();expect(body.name).toBe("Ada");await route.fulfill({status:202,json:{challenge_id:"test-challenge-with-enough-length",email:body.email,expires_in:600,resend_after:60}});});
 await page.route("**/api/auth/register/verify",route=>route.fulfill({status:400,json:{detail:"That code is incorrect. Please try again."}}));
 await page.goto("/login");await page.getByRole("button",{name:"Sign up",exact:true}).click();
 await page.getByLabel("Your name").fill("Ada");await page.getByLabel("Email address").fill("ada@example.com");await page.getByLabel("Password",{exact:true}).fill("strong testing password");
 await page.getByRole("button",{name:"Send verification code"}).click();
 await expect(page.getByRole("heading",{name:"Check your inbox."})).toBeVisible();await expect(page.getByText("ada@example.com")).toBeVisible();await expect(page.getByRole("button",{name:/Resend in/})).toBeDisabled();
 await page.getByLabel("Verification code").fill("123456");await page.getByRole("button",{name:"Verify email & create account"}).click();await expect(page.getByRole("alert",{name:"Signup error"})).toContainText("incorrect");
 await page.screenshot({path:"../docs/screenshots/signup-otp.png",fullPage:true});await page.getByRole("button",{name:"Use a different email"}).click();await expect(page.getByLabel("Email address")).toBeVisible();
});
test("mobile signup does not claim a code was sent when email is unavailable",async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.route("**/api/auth/register",route=>route.fulfill({status:503,json:{detail:"Email verification is not available yet. Please contact the administrator."}}));
 await page.goto("/login");await page.getByRole("button",{name:"Sign up",exact:true}).click();await page.getByLabel("Your name").fill("Ada");await page.getByLabel("Email address").fill("ada@example.com");await page.getByLabel("Password",{exact:true}).fill("strong testing password");await page.getByRole("button",{name:"Send verification code"}).click();await expect(page.getByRole("alert",{name:"Signup error"})).toContainText("not available yet");expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

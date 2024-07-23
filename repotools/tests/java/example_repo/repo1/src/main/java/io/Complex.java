package io;
public class Complex{
    private float r,i;

    public Complex(float r, float i){
        this.r=r;
        this.i=i;
    }

    public float getRealPart(){
        return r;
    }
    public float getImaginary(){
        return i;
    }
    public void setReal(float r){
        this.r=r;
    }
    public void setImaginary(float i){
        this.i=i;
    }
}